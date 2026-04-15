from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class LoraSpec(BaseModel):
    name: str = Field(min_length=1)
    weight: float


class I2IInput(BaseModel):
    source_image: str = Field(min_length=1)
    strength: float | None = Field(default=None, ge=0, le=1)
    mask: str | None = None


class CanonicalGenerateRequest(BaseModel):
    backend: Literal["fal", "bfl"]
    model_ref: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    negative_prompt: str | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    aspect_ratio: str | None = None
    num_inference_steps: int | None = Field(default=None, gt=0)
    guidance_scale: float | None = None
    seed: int | None = None
    num_images: int | None = Field(default=1, gt=0, le=4)
    output_format: Literal["jpeg", "png", "webp"] = "png"
    loras: list[LoraSpec] | None = None
    i2i: I2IInput | None = None
    backend_params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dimensions(self) -> "CanonicalGenerateRequest":
        has_width = self.width is not None
        has_height = self.height is not None
        has_dimensions = has_width or has_height

        if has_dimensions and not (has_width and has_height):
            raise ValueError("width and height must be provided together")

        if has_dimensions and self.aspect_ratio is not None:
            raise ValueError("width/height cannot be set with aspect_ratio")

        return self


class CanonicalImage(BaseModel):
    url: str
    original_url: str | None = None
    local_path: str | None = None
    width: int | None = None
    height: int | None = None
    format: str | None = None


class CanonicalResult(BaseModel):
    images: list[CanonicalImage] = Field(default_factory=list)
    seed_used: int | None = None
    duration_ms: int | None = None
    raw_response: dict[str, Any] | None = None


class JobRecord(BaseModel):
    job_id: str
    proxy_timestamp: datetime
    gateway_version: str
    backend: Literal["fal", "bfl"]
    model_ref: str
    status: Literal["pending", "succeeded", "failed"]
    request: CanonicalGenerateRequest
    result: CanonicalResult | None = None
    error: str | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
