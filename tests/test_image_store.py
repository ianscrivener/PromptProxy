from pathlib import Path

import httpx
import pytest

from gateway.image_store import (
    ImageStoreError,
    _decode_data_url_image,
    _extension_from_content_type,
    persist_result_images,
)
from gateway.models import CanonicalImage, CanonicalResult


@pytest.mark.asyncio
async def test_persist_result_images_uses_content_type_extension(tmp_path):
    async def image_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"image-bytes", headers={"Content-Type": "image/webp"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(image_handler))
    result = CanonicalResult(images=[CanonicalImage(url="https://cdn.example.com/image")])

    updated = await persist_result_images(
        result=result,
        job_id="job-1",
        output_dir=tmp_path,
        static_base_url="http://127.0.0.1:8000/images",
        client=client,
    )
    await client.aclose()

    assert updated.images[0].url.endswith(".webp")
    assert updated.images[0].local_path is not None
    assert Path(updated.images[0].local_path).exists()


@pytest.mark.asyncio
async def test_persist_result_images_raises_on_download_error(tmp_path):
    async def image_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="bad upstream")

    client = httpx.AsyncClient(transport=httpx.MockTransport(image_handler))
    result = CanonicalResult(images=[CanonicalImage(url="https://cdn.example.com/fail.png")])

    with pytest.raises(ImageStoreError):
        await persist_result_images(
            result=result,
            job_id="job-2",
            output_dir=tmp_path,
            static_base_url="http://127.0.0.1:8000/images",
            client=client,
        )
    await client.aclose()


@pytest.mark.asyncio
async def test_persist_result_images_supports_data_url(tmp_path):
    png_data_url = "data:image/png;base64,iVBORw0KGgo="
    result = CanonicalResult(images=[CanonicalImage(url=png_data_url)])

    updated = await persist_result_images(
        result=result,
        job_id="job-3",
        output_dir=tmp_path,
        static_base_url="http://127.0.0.1:8000/images",
        client=None,
    )

    image = updated.images[0]
    assert image.url.endswith("job-3_1.png")
    assert image.local_path is not None
    assert Path(image.local_path).exists()


@pytest.mark.asyncio
async def test_persist_result_images_returns_unchanged_when_no_images(tmp_path):
    result = CanonicalResult(images=[])

    updated = await persist_result_images(
        result=result,
        job_id="job-empty",
        output_dir=tmp_path,
        static_base_url="http://127.0.0.1:8000/images",
        client=None,
    )

    assert updated.images == []


def test_extension_from_content_type_defaults_and_variants():
    assert _extension_from_content_type(None) == ".png"
    assert _extension_from_content_type("image/jpeg") == ".jpg"
    assert _extension_from_content_type("image/webp") == ".webp"
    assert _extension_from_content_type("image/png") == ".png"
    assert _extension_from_content_type("application/octet-stream") == ".png"


def test_decode_data_url_image_errors():
    with pytest.raises(ImageStoreError):
        _decode_data_url_image("data:image/png;base64")

    with pytest.raises(ImageStoreError):
        _decode_data_url_image("data:image/png,abc")

    with pytest.raises(ImageStoreError):
        _decode_data_url_image("data:image/png;base64,%%%")


def test_decode_data_url_image_jpeg_and_webp_extensions():
    jpeg_data, jpeg_ext = _decode_data_url_image("data:image/jpeg;base64,AA==")
    webp_data, webp_ext = _decode_data_url_image("data:image/webp;base64,AA==")

    assert jpeg_data == b"\x00"
    assert jpeg_ext == ".jpg"
    assert webp_data == b"\x00"
    assert webp_ext == ".webp"
