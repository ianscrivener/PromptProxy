from __future__ import annotations

from collections.abc import Iterable

from gateway.plugins.base import BackendAdapter


class AdapterRegistry:
    def __init__(self, adapters: Iterable[BackendAdapter]) -> None:
        self._adapters = {adapter.name: adapter for adapter in adapters}

    def get(self, name: str) -> BackendAdapter | None:
        return self._adapters.get(name)

    def list(self) -> list[BackendAdapter]:
        return list(self._adapters.values())
