from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class JsonlSink:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = asyncio.Lock()

    async def write(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=True)
        async with self._lock:
            await asyncio.to_thread(self._append_line, line)

    def _append_line(self, line: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
