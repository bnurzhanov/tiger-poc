from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .sinks import LocalJsonlSink, validate_process_event


def build_demo_event(index: int, *, source_id: str = "camera-01") -> dict[str, Any]:
    """Create a deterministic ProcessEvent for replay tests."""
    timestamp = datetime(2026, 9, 15, 10, 0, index, tzinfo=UTC)
    event_id = f"evt-{index:04d}"
    return {
        "schemaVersion": "1.0",
        "eventId": event_id,
        "eventType": "ProcessEvent",
        "sourceId": source_id,
        "subjectId": "station-7",
        "observationType": "process-state",
        "value": "running",
        "unit": "status",
        "confidence": 0.99,
        "capturedAt": timestamp.isoformat().replace("+00:00", "Z"),
        "producedAt": timestamp.isoformat().replace("+00:00", "Z"),
        "publishedAt": timestamp.isoformat().replace("+00:00", "Z"),
        "provider": "local-replay",
        "model": "demo-model",
        "source": "replay",
        "sensitive": {"token": "demo-secret"},
    }


def replay_events(events: list[dict[str, Any]], *, output_path: str | Path) -> list[dict[str, Any]]:
    """Publish a deterministic batch of ProcessEvents to a local JSONL sink."""
    sink = LocalJsonlSink(path=output_path)
    published: list[dict[str, Any]] = []
    for event in events:
        validate_process_event(event)
        if sink.publish(event):
            published.append(event)
    return published


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay deterministic ProcessEvent records to a local JSONL sink.")
    parser.add_argument("--output", type=Path, default=Path("replay-process-events.jsonl"), help="Path for the local JSONL sink output")
    parser.add_argument("--count", type=int, default=5, help="Number of deterministic replay events to emit")
    parser.add_argument("--source-id", default="camera-01", help="Source identity to attach to each event")
    return parser


def main() -> int:
    args = create_parser().parse_args()
    events = [build_demo_event(index, source_id=args.source_id) for index in range(1, args.count + 1)]
    output = replay_events(events, output_path=args.output)
    print(json.dumps({"published": len(output), "path": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
