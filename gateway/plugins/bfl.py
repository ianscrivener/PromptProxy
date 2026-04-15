from __future__ import annotations

import asyncio
from time import monotonic
from typing import Any

import httpx

from gateway.models import CanonicalGenerateRequest, CanonicalImage, CanonicalResult
from gateway.plugins.base import BackendAdapter, BackendError


class BflAdapter(BackendAdapter):
    name = "bfl"
    display_name = "BFL"
    supports_i2i = True

    def __init__(
        self,
        api_key: str | None,
        api_base_url: str,
        timeout_seconds: float,
        poll_interval_seconds: float = 0.5,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self._client = client

    async def health_check(self) -> bool:
        return bool(self.api_key)

    async def generate(self, job: CanonicalGenerateRequest) -> CanonicalResult:
        if not self.api_key:
            raise BackendError("BFL_API_KEY is not configured")

        endpoint = f"{self.api_base_url}/{job.model_ref.lstrip('/')}"
        payload = self._build_payload(job)
        submission = await self._post_json(endpoint, payload)

        polling_url = submission.get("polling_url")
        if not isinstance(polling_url, str):
            raise BackendError("BFL submission did not include polling_url")

        data = await self._poll_result(polling_url)
        images = self._extract_images(data)
        if not images:
            raise BackendError("BFL response did not include any image URLs")

        seed = self._extract_seed(data, job.seed)
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
            "x-key": f"{self.api_key}",
            "Content-Type": "application/json",
        }

    async def _post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._post(endpoint, payload)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BackendError(f"BFL request failed: {exc.response.text}") from exc

        return self._parse_json_object(response, context="BFL response")

    async def _get_json(self, url: str) -> dict[str, Any]:
        response = await self._get(url)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BackendError(f"BFL status request failed: {exc.response.text}") from exc

        return self._parse_json_object(response, context="BFL status response")

    @staticmethod
    def _parse_json_object(response: httpx.Response, context: str) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise BackendError(f"{context} was not valid JSON") from exc

        if not isinstance(data, dict):
            raise BackendError(f"{context} was not an object")

        return data

    async def _poll_result(self, polling_url: str) -> dict[str, Any]:
        deadline = monotonic() + self.timeout_seconds

        while True:
            data = await self._get_json(polling_url)
            status = str(data.get("status") or "").strip().lower()

            if status == "ready":
                return data

            if status in {"error", "failed", "canceled", "cancelled"}:
                raise BackendError(f"BFL request failed: {data}")

            if not status and self._extract_images(data):
                # Some endpoints may return the final payload without a status field.
                return data

            if monotonic() >= deadline:
                raise BackendError("Timed out waiting for BFL async result")

            await asyncio.sleep(self.poll_interval_seconds)

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

        if job.i2i is not None:
            model_ref = job.model_ref.lower()

            if "fill" in model_ref:
                payload["image"] = job.i2i.source_image
                if job.i2i.mask is not None:
                    payload["mask"] = job.i2i.mask
            elif "kontext" in model_ref:
                payload["input_image"] = job.i2i.source_image
            else:
                payload["image_prompt"] = job.i2i.source_image
                if job.i2i.strength is not None:
                    payload["image_prompt_strength"] = job.i2i.strength

        payload.update(job.backend_params)
        return payload

    @staticmethod
    def _extract_seed(data: dict[str, Any], fallback_seed: int | None) -> int | None:
        seed = data.get("seed")
        if isinstance(seed, int):
            return seed

        result = data.get("result")
        if isinstance(result, dict):
            nested_seed = result.get("seed")
            if isinstance(nested_seed, int):
                return nested_seed

        return fallback_seed

    @staticmethod
    def _extract_images(data: dict[str, Any]) -> list[CanonicalImage]:
        image_blocks: list[Any] = []

        result = data.get("result")
        if isinstance(result, dict):
            sample = result.get("sample")
            if isinstance(sample, str):
                image_blocks.append(sample)

            samples = result.get("samples")
            if isinstance(samples, list):
                image_blocks.extend(samples)

            result_images = result.get("images")
            if isinstance(result_images, list):
                image_blocks.extend(result_images)

        for candidate in (
            data.get("images"),
            (data.get("output") or {}).get("images") if isinstance(data.get("output"), dict) else None,
        ):
            if isinstance(candidate, list):
                image_blocks.extend(candidate)

        images: list[CanonicalImage] = []
        for item in image_blocks:
            if isinstance(item, str):
                images.append(CanonicalImage(url=item))
                continue

            if not isinstance(item, dict):
                continue

            url = item.get("url") or item.get("image_url") or item.get("sample")
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
