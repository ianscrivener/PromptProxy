import base64
from io import BytesIO

import pytest
from PIL import Image

from gateway.models import CanonicalGenerateRequest
from gateway.plugins.drawthings import DrawThingsAdapter, _SAMPLER_NAME_TO_ID


def _png_data_url(width: int = 128, height: int = 128, color: tuple[int, int, int] = (0, 0, 0)) -> str:
    image = Image.new("RGB", (width, height), color=color)
    buf = BytesIO()
    image.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@pytest.mark.asyncio
async def test_drawthings_adapter_generates_data_url_and_maps_config(monkeypatch):
    captured: dict[str, object] = {}

    class FakeService:
        def __init__(self, address, use_tls=True, use_compression=False):
            captured["address"] = address
            captured["use_tls"] = use_tls
            captured["use_compression"] = use_compression
            self.channel = type("Channel", (), {"close": lambda self: None})()

        def generate(self, prompt, negative_prompt="", config=None, image_bytes=None, mask_bytes=None, timeout=None):
            captured["prompt"] = prompt
            captured["negative_prompt"] = negative_prompt
            captured["config"] = config
            captured["image_bytes"] = image_bytes
            captured["mask_bytes"] = mask_bytes
            captured["timeout"] = timeout
            return [Image.new("RGB", (128, 64), color=(255, 0, 0))]

        def echo(self):
            return object()

        def list_assets(self):
            return {"models": []}

    monkeypatch.setattr("gateway.plugins.drawthings.DTService", FakeService)

    adapter = DrawThingsAdapter(
        address="localhost:7859",
        timeout_seconds=20,
        use_tls=False,
        use_compression=True,
    )

    request = CanonicalGenerateRequest(
        backend="drawthings",
        model_ref="jibmix_zit_v1.0_fp16_f16.ckpt",
        prompt="city at sunset",
        negative_prompt="low quality",
        num_inference_steps=8,
        guidance_scale=1.5,
        seed=42,
        output_format="png",
        backend_params={
            "sampler": "UniPC",
            "clip_skip": 2,
            "timeout_seconds": 30,
        },
    )

    result = await adapter.generate(request)

    assert result.images[0].url.startswith("data:image/png;base64,")
    assert result.images[0].width == 128
    assert result.images[0].height == 64
    assert result.seed_used == 42

    assert captured["address"] == "localhost:7859"
    assert captured["use_tls"] is False
    assert captured["use_compression"] is True
    assert captured["prompt"] == "city at sunset"
    assert captured["negative_prompt"] == "low quality"

    config = captured["config"]
    assert isinstance(config, dict)
    assert config["model"] == "jibmix_zit_v1.0_fp16_f16.ckpt"
    assert config["batch_count"] == 1
    assert config["batch_size"] == 1
    assert config["steps"] == 8
    assert config["guidance_scale"] == 1.5
    assert config["seed"] == 42
    assert config["clip_skip"] == 2
    assert config["sampler"] == _SAMPLER_NAME_TO_ID["UniPC"]
    assert captured["timeout"] == 30.0


@pytest.mark.asyncio
async def test_drawthings_adapter_i2i_passes_source_and_mask_tensors(monkeypatch):
    captured: dict[str, object] = {}

    class FakeService:
        def __init__(self, *args, **kwargs):
            self.channel = type("Channel", (), {"close": lambda self: None})()

        def generate(self, prompt, negative_prompt="", config=None, image_bytes=None, mask_bytes=None, timeout=None):
            captured["config"] = config
            captured["image_bytes"] = image_bytes
            captured["mask_bytes"] = mask_bytes
            return [Image.new("RGB", (64, 64), color=(10, 20, 30))]

        def echo(self):
            return object()

        def list_assets(self):
            return {"models": []}

    monkeypatch.setattr("gateway.plugins.drawthings.DTService", FakeService)

    adapter = DrawThingsAdapter(address="localhost:7859", timeout_seconds=20)

    request = CanonicalGenerateRequest(
        backend="drawthings",
        model_ref="jibmix_zit_v1.0_fp16_f16.ckpt",
        prompt="edit scene",
        i2i={
            "source_image": _png_data_url(128, 128, (80, 90, 100)),
            "mask": _png_data_url(128, 128, (255, 255, 255)),
            "strength": 0.6,
        },
    )

    result = await adapter.generate(request)

    assert result.images
    assert captured["image_bytes"] is not None
    assert captured["mask_bytes"] is not None
    config = captured["config"]
    assert isinstance(config, dict)
    assert config["strength"] == 0.6
    assert config["width"] == 128
    assert config["height"] == 128


@pytest.mark.asyncio
async def test_drawthings_adapter_sampler_fallback_on_no_final_image(monkeypatch):
    calls = {"count": 0}

    class FakeService:
        def __init__(self, *args, **kwargs):
            self.channel = type("Channel", (), {"close": lambda self: None})()

        def generate(self, prompt, negative_prompt="", config=None, image_bytes=None, mask_bytes=None, timeout=None):
            calls["count"] += 1
            if config and config.get("sampler") == _SAMPLER_NAME_TO_ID["UniPC"]:
                raise ValueError("Draw Things did not return a decodable final image (no image tensors returned)")
            return [Image.new("RGB", (96, 96), color=(1, 2, 3))]

        def echo(self):
            return object()

        def list_assets(self):
            return {"models": []}

    monkeypatch.setattr("gateway.plugins.drawthings.DTService", FakeService)

    adapter = DrawThingsAdapter(address="localhost:7859", timeout_seconds=20)

    request = CanonicalGenerateRequest(
        backend="drawthings",
        model_ref="jibmix_zit_v1.0_fp16_f16.ckpt",
        prompt="retry sampler",
        backend_params={"sampler": "UniPC"},
    )

    result = await adapter.generate(request)

    assert calls["count"] == 2
    assert result.raw_response is not None
    assert result.raw_response["sampler_retry"]["from"] == "UniPC"
    assert result.raw_response["sampler_retry"]["to"] == "DPMPP2MTrailing"


@pytest.mark.asyncio
async def test_drawthings_adapter_list_models_parses_metadata(monkeypatch):
    class FakeService:
        def __init__(self, *args, **kwargs):
            self.channel = type("Channel", (), {"close": lambda self: None})()

        def list_assets(self):
            return {
                "models": [
                    {"file": "a.ckpt", "name": "Model A"},
                    {"filename": "b.ckpt", "display_name": "Model B"},
                    "c.ckpt",
                    {"id": 9},
                    {"file": "a.ckpt", "name": "Duplicate A"},
                ]
            }

        def echo(self):
            return object()

    monkeypatch.setattr("gateway.plugins.drawthings.DTService", FakeService)

    adapter = DrawThingsAdapter(address="localhost:7859", timeout_seconds=20)
    models = await adapter.list_models()

    model_refs = [item["model_ref"] for item in models]
    assert model_refs == ["a.ckpt", "b.ckpt", "c.ckpt", "9"]
    assert models[0]["display_name"] == "Model A"
    assert models[1]["display_name"] == "Model B"
