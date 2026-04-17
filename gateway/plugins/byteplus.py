from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from gateway.models import CanonicalGenerateRequest, CanonicalImage, CanonicalResult
from gateway.plugins.base import BackendAdapter, BackendError


_MODEL_SERIES_ALIASES = {
    "seedream50": "seedream50",
    "seedream5": "seedream50",
    "seedream-5-0": "seedream50",
    "seedream 5.0": "seedream50",
    "5.0": "seedream50",
    "5": "seedream50",
    "seedream45": "seedream45",
    "seedream-4-5": "seedream45",
    "seedream 4.5": "seedream45",
    "4.5": "seedream45",
    "seedream40": "seedream40",
    "seedream-4-0": "seedream40",
    "seedream 4.0": "seedream40",
    "4.0": "seedream40",
}


def _canonical_size_pair(width: int, height: int) -> tuple[int, int]:
    if width <= height:
        return (width, height)
    return (height, width)


def _orient_size_pair(
    *,
    requested_width: int,
    requested_height: int,
    canonical_pair: tuple[int, int],
) -> tuple[int, int]:
    small, large = canonical_pair
    if requested_width <= requested_height:
        return (small, large)
    return (large, small)


def _distance_score(
    requested_pair: tuple[int, int],
    candidate_pair: tuple[int, int],
) -> tuple[int, int, int]:
    req_w, req_h = requested_pair
    cand_w, cand_h = candidate_pair
    return (
        abs(req_w - cand_w) + abs(req_h - cand_h),
        abs(req_w * req_h - cand_w * cand_h),
        abs(req_w - cand_w),
    )


def _extract_size_pair(item: Any) -> tuple[int, int] | None:
    if isinstance(item, dict):
        width = item.get("width")
        height = item.get("height")
        if isinstance(width, int) and isinstance(height, int):
            return (width, height)
        return None

    if isinstance(item, list) and len(item) == 2:
        first = item[0]
        second = item[1]
        if isinstance(first, int) and isinstance(second, int):
            return (first, second)

    return None


def _load_allowed_sizes() -> dict[str, set[tuple[int, int]]]:
    config_path = Path(__file__).resolve().parents[2] / "seedream-allowed-sizes.json"
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return {}

    if not isinstance(payload, dict):
        return {}

    parsed: dict[str, set[tuple[int, int]]] = {}
    for series, sizes in payload.items():
        if not isinstance(series, str) or not isinstance(sizes, list):
            continue

        normalized_series = series.strip().lower()
        parsed_sizes: set[tuple[int, int]] = set()
        for item in sizes:
            pair = _extract_size_pair(item)
            if pair is None:
                continue

            width, height = pair
            parsed_sizes.add(_canonical_size_pair(width, height))

        if parsed_sizes:
            parsed[normalized_series] = parsed_sizes

    return parsed


_ALLOWED_SEEDREAM_SIZES = _load_allowed_sizes()
_SIZE_PATTERN = re.compile(r"^\s*(\d+)\s*x\s*(\d+)\s*$", re.IGNORECASE)


class BytePlusAdapter(BackendAdapter):
    name = "byteplus"
    display_name = "BytePlus"
    supports_i2i = True
    supported_models = (
        "seedream-5-0-t2i-250624",
        "seedream-5-0-lite-t2i-250624",
        "seedream-4-5-250905",
        "seedream-4-0-250828",
        "seedream-3-0-t2i-250228",
        "seededit-3-0-i2i-250628",
        "seededit-2-0-i2i",
    )

    def __init__(
        self,
        api_key: str | None,
        api_base_url: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = client

    async def health_check(self) -> bool:
        return bool(self.api_key)

    async def generate(self, job: CanonicalGenerateRequest) -> CanonicalResult:
        if not self.api_key:
            raise BackendError("BYTEPLUS_ARK_API_KEY (or ARK_API_KEY) is not configured")

        endpoint = f"{self.api_base_url}/images/generations"
        payload = self._build_payload(job)
        raw_data = await self._post_json(endpoint, payload)
        data = self._unwrap_response_body(raw_data)

        images = self._extract_images(data)
        if not images:
            raise BackendError("BytePlus response did not include any image URLs")

        seed = self._extract_seed(data, fallback_seed=job.seed)
        debug_request = {
            "method": "POST",
            "url": endpoint,
            "headers": {"Content-Type": "application/json"},
            "payload": payload,
        }
        return CanonicalResult(
            images=images,
            seed_used=seed,
            raw_request=debug_request,
            raw_response=data,
        )

    async def _post(self, endpoint: str, payload: dict[str, Any]) -> httpx.Response:
        headers = self._auth_headers()

        if self._client is not None:
            return await self._client.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )

        async with httpx.AsyncClient(follow_redirects=True) as client:
            return await client.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._post(endpoint, payload)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BackendError(f"BytePlus request failed: {exc.response.text}") from exc

        return self._parse_json_object(response, context="BytePlus response")

    @staticmethod
    def _parse_json_object(response: httpx.Response, context: str) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise BackendError(f"{context} was not valid JSON") from exc

        if not isinstance(data, dict):
            raise BackendError(f"{context} was not an object")

        return data

    def _build_payload(self, job: CanonicalGenerateRequest) -> dict[str, Any]:
        if job.loras:
            raise BackendError("BytePlus adapter does not support LoRA inputs")

        if job.i2i is not None and job.i2i.mask is not None:
            raise BackendError("BytePlus adapter does not support i2i masks")

        backend_params = dict(job.backend_params)
        raw_model_series = backend_params.pop("model_series", None)
        payload: dict[str, Any] = {
            "model": job.model_ref,
            "prompt": job.prompt,
            "response_format": "url",
        }

        if job.num_images is not None:
            payload["n"] = job.num_images

        if job.seed is not None:
            payload["seed"] = job.seed

        if job.guidance_scale is not None:
            payload["guidance_scale"] = job.guidance_scale

        if job.i2i is not None:
            payload["image"] = job.i2i.source_image

        raw_size = backend_params.pop("size", None)
        if raw_size is not None:
            normalized_size = self._normalize_size(raw_size)
            model_series = self._resolve_model_series(raw_model_series, job.model_ref)
            payload["size"] = self._normalize_size_for_model(
                size=normalized_size,
                model_series=model_series,
            )
        elif job.i2i is not None:
            payload["size"] = "adaptive"
        else:
            payload["size"] = "2K"

        payload.update(backend_params)
        # Keep canonical request fields authoritative.
        payload["model"] = job.model_ref
        payload["prompt"] = job.prompt
        return payload

    @staticmethod
    def _unwrap_response_body(data: dict[str, Any]) -> dict[str, Any]:
        wrapped_body = data.get("body")
        if isinstance(wrapped_body, dict):
            return wrapped_body
        return data

    @staticmethod
    def _extract_seed(data: dict[str, Any], fallback_seed: int | None) -> int | None:
        seed = data.get("seed")
        if isinstance(seed, int):
            return seed

        image_data = data.get("data")
        if isinstance(image_data, list):
            for item in image_data:
                if isinstance(item, dict):
                    nested_seed = item.get("seed")
                    if isinstance(nested_seed, int):
                        return nested_seed

        return fallback_seed

    @staticmethod
    def _extract_images(data: dict[str, Any]) -> list[CanonicalImage]:
        image_blocks: list[Any] = []

        raw_data = data.get("data")
        if isinstance(raw_data, list):
            image_blocks.extend(raw_data)

        fallback_images = data.get("images")
        if isinstance(fallback_images, list):
            image_blocks.extend(fallback_images)

        images: list[CanonicalImage] = []
        for item in image_blocks:
            if isinstance(item, str):
                images.append(CanonicalImage(url=item))
                continue

            if not isinstance(item, dict):
                continue

            width = item.get("width") if isinstance(item.get("width"), int) else None
            height = item.get("height") if isinstance(item.get("height"), int) else None
            fmt = item.get("format") if isinstance(item.get("format"), str) else None

            url = item.get("url")
            if isinstance(url, str) and url:
                images.append(
                    CanonicalImage(
                        url=url,
                        width=width,
                        height=height,
                        format=fmt,
                    )
                )
                continue

            b64_json = item.get("b64_json")
            if isinstance(b64_json, str) and b64_json:
                images.append(
                    CanonicalImage(
                        url=f"data:image/png;base64,{b64_json}",
                        width=width,
                        height=height,
                        format=fmt or "png",
                    )
                )

        return images

    @staticmethod
    def _normalize_size(value: Any) -> str:
        if not isinstance(value, str):
            raise BackendError("BytePlus size must be a string")

        trimmed = value.strip()
        if not trimmed:
            raise BackendError("BytePlus size cannot be empty")

        if trimmed.lower() == "adaptive":
            return "adaptive"

        normalized = trimmed.upper()
        if normalized in {"1K", "2K", "4K"}:
            return normalized

        custom_match = _SIZE_PATTERN.match(trimmed)
        if custom_match is not None:
            width = int(custom_match.group(1))
            height = int(custom_match.group(2))
            if width <= 0 or height <= 0:
                raise BackendError(f"Unsupported BytePlus size: {trimmed}")
            return f"{width}x{height}"

        raise BackendError(f"Unsupported BytePlus size: {trimmed}")

    @staticmethod
    def _parse_custom_size(size: str) -> tuple[int, int] | None:
        match = _SIZE_PATTERN.match(size)
        if match is None:
            return None
        return int(match.group(1)), int(match.group(2))

    def _normalize_size_for_model(self, size: str, model_series: str | None) -> str:
        parsed = self._parse_custom_size(size)
        if parsed is None or model_series is None:
            return size

        width, height = parsed
        resolved_width, resolved_height = self._resolve_allowed_size(
            width=width,
            height=height,
            model_series=model_series,
        )
        return f"{resolved_width}x{resolved_height}"

    @staticmethod
    def _normalize_model_series(value: Any) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise BackendError("BytePlus model_series must be a string")

        trimmed = value.strip().lower()
        if not trimmed:
            raise BackendError("BytePlus model_series cannot be empty")

        normalized = _MODEL_SERIES_ALIASES.get(trimmed)
        if normalized is None:
            allowed = ", ".join(sorted({"seedream50", "seedream45", "seedream40"}))
            raise BackendError(
                f"Unsupported BytePlus model_series: {value}. Allowed values: {allowed}"
            )

        return normalized

    @classmethod
    def _resolve_model_series(cls, model_series: Any, model_ref: str) -> str | None:
        normalized = cls._normalize_model_series(model_series)
        if normalized is not None:
            return normalized

        ref = model_ref.strip().lower()
        if "seedream-5-0" in ref:
            return "seedream50"
        if "seedream-4-5" in ref:
            return "seedream45"
        if "seedream-4-0" in ref:
            return "seedream40"

        return None

    @staticmethod
    def _resolve_allowed_size(width: int, height: int, model_series: str) -> tuple[int, int]:
        allowed = _ALLOWED_SEEDREAM_SIZES.get(model_series)
        if not allowed:
            raise BackendError(
                f"No allowed-size configuration found for BytePlus model_series: {model_series}"
            )

        requested_canonical = _canonical_size_pair(width, height)
        if requested_canonical in allowed:
            return (width, height)

        best_pair: tuple[int, int] | None = None
        best_score: tuple[int, int, int] = (10**12, 10**18, 10**12)
        for candidate in allowed:
            score = _distance_score(requested_canonical, candidate)
            if score < best_score:
                best_pair = candidate
                best_score = score

        if best_pair is None:
            allowed_values = ", ".join(sorted(f"{w}x{h}" for w, h in allowed))
            raise BackendError(
                f"Unsupported BytePlus dimensions {width}x{height} for {model_series}. "
                f"Allowed size pairs: {allowed_values} (orientation can be swapped)"
            )

        return _orient_size_pair(
            requested_width=width,
            requested_height=height,
            canonical_pair=best_pair,
        )
