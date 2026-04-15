from __future__ import annotations

from abc import ABC, abstractmethod

from gateway.models import CanonicalGenerateRequest, CanonicalResult


class BackendError(RuntimeError):
    """Raised when an upstream backend fails."""


class BackendAdapter(ABC):
    name: str
    display_name: str
    supports_i2i: bool = False
    supports_loras: bool = False

    @abstractmethod
    async def health_check(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def generate(self, job: CanonicalGenerateRequest) -> CanonicalResult:
        raise NotImplementedError
