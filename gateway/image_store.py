from __future__ import annotations

import asyncio
import base64
import binascii
from pathlib import Path
from urllib.parse import urlparse

import httpx

from gateway.models import CanonicalImage, CanonicalResult


class ImageStoreError(RuntimeError):
    """Raised when image persistence fails."""


def _extension_from_url(url: str) -> str | None:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return suffix
    return None


def _extension_from_content_type(content_type: str | None) -> str:
    if not content_type:
        return ".png"

    lowered = content_type.lower()
    if "image/jpeg" in lowered:
        return ".jpg"
    if "image/webp" in lowered:
        return ".webp"
    if "image/png" in lowered:
        return ".png"
    return ".png"


def _is_data_url(value: str) -> bool:
    return value.startswith("data:image/")


def _decode_data_url_image(data_url: str) -> tuple[bytes, str]:
    if "," not in data_url:
        raise ImageStoreError("Invalid data URL image format")

    meta, encoded = data_url.split(",", 1)
    if ";base64" not in meta:
        raise ImageStoreError("Unsupported non-base64 data URL image")

    mime = meta[5:].split(";", 1)[0].lower()
    if mime == "image/jpeg":
        ext = ".jpg"
    elif mime == "image/webp":
        ext = ".webp"
    else:
        ext = ".png"

    try:
        content = base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise ImageStoreError("Invalid base64 image data in data URL") from exc

    return content, ext


async def persist_result_images(
    result: CanonicalResult,
    job_id: str,
    output_dir: Path,
    static_base_url: str,
    client: httpx.AsyncClient | None = None,
) -> CanonicalResult:
    if not result.images:
        return result

    output_dir.mkdir(parents=True, exist_ok=True)

    managed_client = client
    created_client = False
    if managed_client is None:
        managed_client = httpx.AsyncClient(follow_redirects=True)
        created_client = True

    updated_images: list[CanonicalImage] = []

    try:
        for index, image in enumerate(result.images, start=1):
            if _is_data_url(image.url):
                content, ext = _decode_data_url_image(image.url)
            else:
                response = await managed_client.get(image.url, timeout=120)
                response.raise_for_status()

                content = response.content
                ext = _extension_from_url(image.url)
                if ext is None:
                    ext = _extension_from_content_type(response.headers.get("Content-Type"))

            filename = f"{job_id}_{index}{ext}"
            local_path = output_dir / filename
            await asyncio.to_thread(local_path.write_bytes, content)

            local_url = f"{static_base_url.rstrip('/')}/{filename}"
            updated_images.append(
                image.model_copy(
                    update={
                        "original_url": image.url,
                        "url": local_url,
                        "local_path": str(local_path),
                    }
                )
            )
    except httpx.HTTPError as exc:
        raise ImageStoreError(f"Failed to persist image: {exc}") from exc
    finally:
        if created_client and managed_client is not None:
            await managed_client.aclose()

    return result.model_copy(update={"images": updated_images})
