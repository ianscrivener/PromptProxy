from __future__ import annotations

import asyncio
from time import monotonic
from typing import Any

import httpx

from gateway.models import CanonicalGenerateRequest, CanonicalImage, CanonicalResult
from gateway.plugins.base import BackendAdapter, BackendError


class FalAdapter(BackendAdapter):
    name = "fal"
    display_name = "FAL"
    supports_i2i = True
    supports_loras = True
    supported_models = (
        "fal-ai/flux/dev",
        "fal-ai/flux/schnell",
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
            raise BackendError("FAL_KEY is not configured")

        endpoint = f"{self.api_base_url}/{job.model_ref.lstrip('/')}"
        payload = self._build_payload(job)
        response = await self._post(endpoint, payload)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BackendError(f"FAL request failed: {exc.response.text}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise BackendError("FAL response was not valid JSON") from exc

        if self._is_async_submission(data):
            data = await self._resolve_async_result(data)

        images = self._extract_images(data)
        if not images:
            raise BackendError("FAL response did not include any image URLs")

        seed = self._extract_seed(data)
        return CanonicalResult(images=images, seed_used=seed, raw_response=data)

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

    async def _get(self, url: str) -> httpx.Response:
        headers = self._auth_headers()

        if self._client is not None:
            return await self._client.get(
                url,
                headers=headers,
                timeout=self.timeout_seconds,
            )

        async with httpx.AsyncClient(follow_redirects=True) as client:
            return await client.get(
                url,
                headers=headers,
                timeout=self.timeout_seconds,
            )

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _is_async_submission(data: dict[str, Any]) -> bool:
        return isinstance(data, dict) and (
            isinstance(data.get("response_url"), str)
            or isinstance(data.get("status_url"), str)
            or data.get("status") in {"IN_QUEUE", "IN_PROGRESS"}
        )

    async def _resolve_async_result(self, submission: dict[str, Any]) -> dict[str, Any]:
        status_url = submission.get("status_url")
        response_url = submission.get("response_url")

        if not isinstance(response_url, str):
            raise BackendError("FAL async response did not include response_url")

        deadline = monotonic() + self.timeout_seconds

        if isinstance(status_url, str):
            while True:
                status_data = await self._get_json(status_url)
                status = status_data.get("status")

                if status == "COMPLETED":
                    break

                if status in {"FAILED", "CANCELED"}:
                    raise BackendError(f"FAL request {status.lower()}: {status_data}")

                if monotonic() >= deadline:
                    raise BackendError("Timed out waiting for FAL async result")

                await asyncio.sleep(1)

        result = await self._get_json(response_url)

        if self._is_async_submission(result):
            # Some queue endpoints may return intermediate status even on response_url.
            while self._is_async_submission(result):
                status = result.get("status")
                if status in {"FAILED", "CANCELED"}:
                    raise BackendError(f"FAL request {status.lower()}: {result}")

                if monotonic() >= deadline:
                    raise BackendError("Timed out waiting for FAL async result")

                await asyncio.sleep(1)
                result = await self._get_json(response_url)

        return result

    async def _get_json(self, url: str) -> dict[str, Any]:
        response = await self._get(url)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BackendError(f"FAL status request failed: {exc.response.text}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise BackendError("FAL status response was not valid JSON") from exc

        if not isinstance(data, dict):
            raise BackendError("FAL status response was not an object")

        return data

    def _build_payload(self, job: CanonicalGenerateRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {"prompt": job.prompt}

        for field_name in (
            "negative_prompt",
            "width",
            "height",
            "aspect_ratio",
            "num_inference_steps",
            "guidance_scale",
            "seed",
            "num_images",
            "output_format",
        ):
            value = getattr(job, field_name)
            if value is not None:
                payload[field_name] = value

        if job.loras:
            payload["loras"] = [item.model_dump(mode="json") for item in job.loras]

        if job.i2i is not None:
            payload["image_url"] = job.i2i.source_image
            if job.i2i.strength is not None:
                payload["strength"] = job.i2i.strength
            if job.i2i.mask is not None:
                payload["mask_url"] = job.i2i.mask

        payload.update(job.backend_params)
        return payload

    @staticmethod
    def _extract_seed(data: dict[str, Any]) -> int | None:
        seed = data.get("seed")
        if isinstance(seed, int):
            return seed

        nested = data.get("data")
        if isinstance(nested, dict):
            nested_seed = nested.get("seed")
            if isinstance(nested_seed, int):
                return nested_seed

        return None

    @staticmethod
    def _extract_images(data: dict[str, Any]) -> list[CanonicalImage]:
        image_blocks: list[Any] = []

        for candidate in (
            data.get("images"),
            (data.get("data") or {}).get("images") if isinstance(data.get("data"), dict) else None,
            (data.get("output") or {}).get("images") if isinstance(data.get("output"), dict) else None,
        ):
            if isinstance(candidate, list):
                image_blocks.extend(candidate)

        single_image = data.get("image")
        if isinstance(single_image, str):
            image_blocks.append(single_image)

        images: list[CanonicalImage] = []
        for item in image_blocks:
            if isinstance(item, str):
                images.append(CanonicalImage(url=item))
                continue

            if not isinstance(item, dict):
                continue

            url = item.get("url") or item.get("image_url")
            nested_image = item.get("image")
            if url is None and isinstance(nested_image, dict):
                url = nested_image.get("url")

            if not isinstance(url, str):
                continue

            width = item.get("width") if isinstance(item.get("width"), int) else None
            height = item.get("height") if isinstance(item.get("height"), int) else None
            fmt = item.get("format") if isinstance(item.get("format"), str) else None
            images.append(
                CanonicalImage(
                    url=url,
                    width=width,
                    height=height,
                    format=fmt,
                )
            )

        return images
