import json

import pytest

from gateway.sinks.jsonl import JsonlSink


@pytest.mark.asyncio
async def test_jsonl_sink_appends_lines(tmp_path):
    sink_path = tmp_path / "logs" / "events.jsonl"
    sink = JsonlSink(sink_path)

    await sink.write({"event": "dispatch", "job_id": "1"})
    await sink.write({"event": "completion", "job_id": "1", "status": "succeeded"})

    lines = sink_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "dispatch"
    assert json.loads(lines[1])["event"] == "completion"
