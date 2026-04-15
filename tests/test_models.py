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
