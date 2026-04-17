import pytest
from pydantic import ValidationError

from gateway.models import CanonicalGenerateRequest


def test_request_accepts_aspect_ratio():
    request = CanonicalGenerateRequest(
        backend="fal",
        model_ref="fal-ai/flux/dev",
        prompt="test",
        aspect_ratio="16:9",
    )

    assert request.aspect_ratio == "16:9"
    assert request.width is None
    assert request.height is None


def test_request_accepts_bfl_backend():
    request = CanonicalGenerateRequest(
        backend="bfl",
        model_ref="flux-2-pro",
        prompt="test",
    )

    assert request.backend == "bfl"


def test_request_accepts_drawthings_backend():
    request = CanonicalGenerateRequest(
        backend="drawthings",
        model_ref="jibmix_zit_v1.0_fp16_f16.ckpt",
        prompt="test",
    )

    assert request.backend == "drawthings"


def test_request_accepts_byteplus_backend():
    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="seedream-5-0-t2i-250624",
        prompt="test",
    )

    assert request.backend == "byteplus"


def test_request_rejects_partial_dimensions():
    with pytest.raises(ValidationError):
        CanonicalGenerateRequest(
            backend="fal",
            model_ref="fal-ai/flux/dev",
            prompt="test",
            width=1024,
        )


def test_request_rejects_dimensions_with_aspect_ratio():
    with pytest.raises(ValidationError):
        CanonicalGenerateRequest(
            backend="fal",
            model_ref="fal-ai/flux/dev",
            prompt="test",
            width=1024,
            height=1024,
            aspect_ratio="1:1",
        )
