from __future__ import annotations

import asyncio
import base64
import binascii
from io import BytesIO
from pathlib import Path
from time import monotonic
from typing import Any

import grpc
import httpx
from PIL import Image

from gateway.drawthings import DTService, SAMPLER_OPTIONS
from gateway.drawthings.image_helpers import convert_image_for_request
from gateway.models import CanonicalGenerateRequest, CanonicalImage, CanonicalResult
from gateway.plugins.base import BackendAdapter, BackendError


DEFAULT_UPSCALE_MODEL = "4x_ultrasharp_f16.ckpt"
DEFAULT_FACE_RESTORE_MODEL = "RestoreFormer.pth"
_FALSE_VALUES = {"0", "false", "no", "off", "none", "null"}
_TRUE_VALUES = {"1", "true", "yes", "on"}

_SAMPLER_NAME_TO_ID: dict[str, int] = {
    str(item["api_name"]): int(item["id"])
    for item in SAMPLER_OPTIONS
}
_SAMPLER_ID_TO_NAME: dict[int, str] = {
    sampler_id: sampler_name for sampler_name, sampler_id in _SAMPLER_NAME_TO_ID.items()
}
_SAMPLER_FALLBACKS: dict[str, tuple[str, ...]] = {
    "UniPC": ("DPMPP2MTrailing", "DPMPP2MKarras"),
}


class DrawThingsAdapter(BackendAdapter):
    name = "drawthings"
    display_name = "DrawThings"
    supports_i2i = True
    supports_loras = True
    supported_models: tuple[str, ...] = ()

    def __init__(
        self,
        address: str,
        timeout_seconds: float,
        use_tls: bool = True,
        use_compression: bool = False,
        enabled: bool = True,
        health_check_timeout_seconds: float = 2.0,
    ) -> None:
        self.address = address
        self.timeout_seconds = timeout_seconds
        self.use_tls = use_tls
        self.use_compression = use_compression
        self.enabled = enabled
        self.health_check_timeout_seconds = health_check_timeout_seconds

    async def health_check(self) -> bool:
        if not self.enabled:
            return False

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._echo_sync),
                timeout=self.health_check_timeout_seconds,
            )
        except Exception:
            return False

    async def generate(self, job: CanonicalGenerateRequest) -> CanonicalResult:
        if not self.enabled:
            raise BackendError("DrawThings backend is disabled")

        config, timeout_seconds = self._build_config(job)

        source_bytes: bytes | None = None
        mask_bytes: bytes | None = None
        if job.i2i is not None:
            source_bytes = await self._load_image_bytes(job.i2i.source_image)
            if job.i2i.mask is not None:
                mask_bytes = await self._load_image_bytes(job.i2i.mask)

        started = monotonic()
        try:
            images, sampler_retry = await asyncio.to_thread(
                self._generate_sync,
                job,
                config,
                timeout_seconds,
                source_bytes,
                mask_bytes,
            )
        except grpc.RpcError as exc:
            raise BackendError(self._format_rpc_error(exc)) from exc
        except TimeoutError as exc:
            raise BackendError(str(exc)) from exc
        except BackendError:
            raise
        except Exception as exc:
            raise BackendError(f"DrawThings generation failed: {exc}") from exc

        if not images:
            raise BackendError("DrawThings did not return any images")

        canonical_images = [self._to_canonical_image(image, job.output_format) for image in images]

        raw_response: dict[str, Any] = {
            "provider": self.name,
            "image_count": len(canonical_images),
            "address": self.address,
        }
        if sampler_retry is not None:
            raw_response["sampler_retry"] = sampler_retry

        return CanonicalResult(
            images=canonical_images,
            seed_used=job.seed,
            duration_ms=int((monotonic() - started) * 1000),
            raw_response=raw_response,
        )

    async def list_models(self) -> list[dict[str, str | None]]:
        if not self.enabled:
            return []

        try:
            assets = await asyncio.to_thread(self._list_assets_sync)
        except Exception:
            return []

        raw_models = assets.get("models") if isinstance(assets, dict) else None
        if not isinstance(raw_models, list):
            return []

        models: list[dict[str, str | None]] = []
        seen_model_refs: set[str] = set()

        for item in raw_models:
            model_ref = self._model_ref(item)
            if not model_ref or model_ref in seen_model_refs:
                continue

            seen_model_refs.add(model_ref)
            models.append(
                {
                    "model_ref": model_ref,
                    "display_name": self._display_name(item),
                }
            )

        return models

    def _echo_sync(self) -> bool:
        service = self._service()
        try:
            service.echo()
            return True
        finally:
            self._close_service(service)

    def _list_assets_sync(self) -> dict[str, Any]:
        service = self._service()
        try:
            assets = service.list_assets()
            if isinstance(assets, dict):
                return assets
            return {}
        finally:
            self._close_service(service)

    def _generate_sync(
        self,
        job: CanonicalGenerateRequest,
        config: dict[str, Any],
        timeout_seconds: float,
        source_bytes: bytes | None,
        mask_bytes: bytes | None,
    ) -> tuple[list[Image.Image], dict[str, str] | None]:
        service = self._service()

        try:
            return self._generate_with_optional_sampler_fallback(
                service=service,
                job=job,
                config=config,
                timeout_seconds=timeout_seconds,
                source_bytes=source_bytes,
                mask_bytes=mask_bytes,
            )
        finally:
            self._close_service(service)

    def _generate_with_optional_sampler_fallback(
        self,
        service: DTService,
        job: CanonicalGenerateRequest,
        config: dict[str, Any],
        timeout_seconds: float,
        source_bytes: bytes | None,
        mask_bytes: bytes | None,
    ) -> tuple[list[Image.Image], dict[str, str] | None]:
        try:
            images = self._run_generation(
                service=service,
                job=job,
                config=config,
                timeout_seconds=timeout_seconds,
                source_bytes=source_bytes,
                mask_bytes=mask_bytes,
            )
            return images, None
        except Exception as exc:
            if not self._is_no_final_image_error(exc):
                raise

            current_sampler_name = self._sampler_name(config.get("sampler"))
            if current_sampler_name is None:
                raise

            fallback_names = _SAMPLER_FALLBACKS.get(current_sampler_name, ())
            if not fallback_names:
                raise

            last_error: Exception = exc
            for fallback_name in fallback_names:
                fallback_sampler = _SAMPLER_NAME_TO_ID.get(fallback_name)
                if fallback_sampler is None:
                    continue

                retry_config = dict(config)
                retry_config["sampler"] = fallback_sampler

                try:
                    images = self._run_generation(
                        service=service,
                        job=job,
                        config=retry_config,
                        timeout_seconds=timeout_seconds,
                        source_bytes=source_bytes,
                        mask_bytes=mask_bytes,
                    )
                    return images, {"from": current_sampler_name, "to": fallback_name}
                except Exception as retry_exc:
                    last_error = retry_exc

            raise last_error

    def _run_generation(
        self,
        service: DTService,
        job: CanonicalGenerateRequest,
        config: dict[str, Any],
        timeout_seconds: float,
        source_bytes: bytes | None,
        mask_bytes: bytes | None,
    ) -> list[Image.Image]:
        timeout = None if timeout_seconds <= 0 else timeout_seconds

        if source_bytes is None:
            return service.generate(
                prompt=job.prompt,
                negative_prompt=job.negative_prompt or "",
                config=config,
                timeout=timeout,
            )

        source_image = self._bytes_to_image(source_bytes)

        width = self._round64(int(config.get("width") or source_image.width))
        height = self._round64(int(config.get("height") or source_image.height))

        resolved_config = dict(config)
        resolved_config["width"] = width
        resolved_config["height"] = height

        image_tensor = convert_image_for_request(source_image, width=width, height=height)

        mask_tensor: bytes | None = None
        if mask_bytes is not None:
            mask_image = self._bytes_to_image(mask_bytes)
            mask_tensor = convert_image_for_request(mask_image, width=width, height=height)

        return service.generate(
            prompt=job.prompt,
            negative_prompt=job.negative_prompt or "",
            config=resolved_config,
            image_bytes=image_tensor,
            mask_bytes=mask_tensor,
            timeout=timeout,
        )

    def _build_config(self, job: CanonicalGenerateRequest) -> tuple[dict[str, Any], float]:
        backend_params = dict(job.backend_params)

        config: dict[str, Any] = {
            "model": job.model_ref,
            "batch_count": 1,
            "batch_size": 1,
            "seed": -1 if job.seed is None else job.seed,
        }

        if job.width is not None:
            config["width"] = job.width
        if job.height is not None:
            config["height"] = job.height
        if job.num_inference_steps is not None:
            config["steps"] = job.num_inference_steps
        if job.guidance_scale is not None:
            config["guidance_scale"] = job.guidance_scale
        if job.i2i is not None and job.i2i.strength is not None:
            config["strength"] = job.i2i.strength
        if job.loras:
            config["loras"] = [
                {
                    "file": item.name,
                    "weight": item.weight,
                }
                for item in job.loras
            ]

        timeout_seconds = self.timeout_seconds
        raw_timeout = backend_params.pop("timeout_seconds", None)
        if raw_timeout is not None:
            timeout_seconds = self._to_float(raw_timeout, field_name="timeout_seconds")

        raw_sampler = backend_params.pop("sampler_name", None)
        if raw_sampler is None:
            raw_sampler = backend_params.get("sampler")
        if raw_sampler is not None:
            config["sampler"] = self._normalize_sampler(raw_sampler)
            backend_params.pop("sampler", None)

        raw_upscaler = backend_params.pop("upscaler", None)
        if raw_upscaler is not None:
            resolved_upscaler = self._resolve_optional_model(raw_upscaler, default_model=DEFAULT_UPSCALE_MODEL)
            if resolved_upscaler:
                config["upscaler"] = resolved_upscaler

        raw_face_restore = backend_params.pop("face_restore", None)
        if raw_face_restore is None:
            raw_face_restore = backend_params.pop("facefix", None)
        if raw_face_restore is None:
            raw_face_restore = backend_params.pop("face_restoration", None)
        if raw_face_restore is not None:
            resolved_face_restore = self._resolve_optional_model(
                raw_face_restore,
                default_model=DEFAULT_FACE_RESTORE_MODEL,
            )
            if resolved_face_restore:
                config["face_restoration"] = resolved_face_restore

        config.update(backend_params)
        return config, timeout_seconds

    async def _load_image_bytes(self, source: str) -> bytes:
        if source.startswith("data:"):
            return self._decode_data_url(source)

        if source.startswith("http://") or source.startswith("https://"):
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(source, timeout=self.timeout_seconds)
                response.raise_for_status()
                return response.content

        path = Path(source).expanduser()
        if not path.is_absolute():
            path = path.resolve()
        if not path.exists():
            raise BackendError(f"Image path does not exist: {source}")
        return await asyncio.to_thread(path.read_bytes)

    @staticmethod
    def _decode_data_url(data_url: str) -> bytes:
        if "," not in data_url:
            raise BackendError("Invalid data URL image format")

        meta, encoded = data_url.split(",", 1)
        if not meta.lower().startswith("data:image/"):
            raise BackendError("Only image data URLs are supported")
        if ";base64" not in meta:
            raise BackendError("Unsupported non-base64 data URL image")

        try:
            return base64.b64decode(encoded, validate=True)
        except binascii.Error as exc:
            raise BackendError("Invalid base64 data URL image") from exc

    @staticmethod
    def _bytes_to_image(payload: bytes) -> Image.Image:
        with Image.open(BytesIO(payload)) as image:
            return image.convert("RGB")

    @staticmethod
    def _to_canonical_image(image: Image.Image, output_format: str) -> CanonicalImage:
        fmt = output_format.lower()
        if fmt == "jpeg":
            pil_format = "JPEG"
            mime = "image/jpeg"
            image = image.convert("RGB")
        elif fmt == "webp":
            pil_format = "WEBP"
            mime = "image/webp"
            image = image.convert("RGB")
        else:
            pil_format = "PNG"
            mime = "image/png"

        buffer = BytesIO()
        image.save(buffer, format=pil_format)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

        return CanonicalImage(
            url=f"data:{mime};base64,{encoded}",
            width=image.width,
            height=image.height,
            format=output_format,
        )

    @staticmethod
    def _normalize_sampler(value: Any) -> int:
        if isinstance(value, int):
            if value in _SAMPLER_ID_TO_NAME:
                return value
            raise BackendError(f"Unsupported DrawThings sampler id: {value}")

        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                raise BackendError("DrawThings sampler cannot be empty")

            if trimmed.isdigit():
                sampler_id = int(trimmed)
                if sampler_id in _SAMPLER_ID_TO_NAME:
                    return sampler_id
                raise BackendError(f"Unsupported DrawThings sampler id: {sampler_id}")

            if trimmed in _SAMPLER_NAME_TO_ID:
                return _SAMPLER_NAME_TO_ID[trimmed]

            raise BackendError(
                f"Unsupported DrawThings sampler: {trimmed}. "
                f"Supported values: {', '.join(sorted(_SAMPLER_NAME_TO_ID))}"
            )

        raise BackendError("DrawThings sampler must be a name or id")

    @staticmethod
    def _resolve_optional_model(value: Any, default_model: str) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return default_model if value else None

        lowered = str(value).strip().lower()
        if lowered in _TRUE_VALUES:
            return default_model
        if lowered in _FALSE_VALUES:
            return None

        resolved = str(value).strip()
        if not resolved:
            return None
        return resolved

    @staticmethod
    def _sampler_name(sampler_value: Any) -> str | None:
        if isinstance(sampler_value, int):
            return _SAMPLER_ID_TO_NAME.get(sampler_value)
        if isinstance(sampler_value, str) and sampler_value in _SAMPLER_NAME_TO_ID:
            return sampler_value
        return None

    @staticmethod
    def _is_no_final_image_error(exc: Exception) -> bool:
        return "did not return a decodable final image" in str(exc)

    @staticmethod
    def _round64(value: int) -> int:
        return max(round(value / 64) * 64, 64)

    @staticmethod
    def _to_float(value: Any, field_name: str) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise BackendError(f"Invalid numeric value for {field_name}: {value}") from exc

    @staticmethod
    def _model_ref(item: Any) -> str | None:
        if isinstance(item, dict):
            for key in ("file", "filename", "name", "id"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    return value
                if isinstance(value, int):
                    return str(value)
            return None

        if isinstance(item, str) and item:
            return item

        return None

    @staticmethod
    def _display_name(item: Any) -> str | None:
        if not isinstance(item, dict):
            return None

        for key in ("display_name", "name", "label", "title"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value

        return None

    def _service(self) -> DTService:
        return DTService(
            address=self.address,
            use_tls=self.use_tls,
            use_compression=self.use_compression,
        )

    @staticmethod
    def _close_service(service: DTService) -> None:
        channel = getattr(service, "channel", None)
        if channel is not None and hasattr(channel, "close"):
            channel.close()

    @staticmethod
    def _format_rpc_error(exc: grpc.RpcError) -> str:
        details_method = getattr(exc, "details", None)
        code_method = getattr(exc, "code", None)

        details = details_method() if callable(details_method) else str(exc)
        code = code_method() if callable(code_method) else None
        code_name = getattr(code, "name", "UNKNOWN")

        return f"DrawThings gRPC {code_name}: {details}"
