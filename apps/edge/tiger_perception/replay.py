"""Deterministic multi-cell event replay and live event simulation generator."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .contracts import ProcessEvent
from .sinks import FabricEventstreamSink, LocalJsonlSink, validate_process_event

logger = logging.getLogger(__name__)


def generate_scenario_events(
    start_time: datetime | None = None,
    plant_name: str = "Demo Plant 01",
    plant_id: str = "demo-plant-01",
) -> list[dict[str, Any]]:
    """Generate a sequence of realistic multi-cell pallet transitions.

    Sequence:
    1. Cell A initialized Empty (t=0s)
    2. Cell B initialized Empty (t=0s)
    3. Pallet placed in Cell A (t=+5s, occupied=True)
    4. Pallet placed in Cell B (t=+12s, occupied=True)
    5. Pallet removed from Cell A (t=+20s, occupied=False)
    6. Pallet removed from Cell B (t=+28s, occupied=False)
    """
    base_t = start_time or datetime.now(UTC)
    transitions = [
        # (offset_sec, source_id, subject_id, occupied, confidence)
        (0, "cell-a-camera-01", "cell-a-pallet-position-01", False, 1.0),
        (0, "cell-b-camera-01", "cell-b-pallet-position-01", False, 1.0),
        (5, "cell-a-camera-01", "cell-a-pallet-position-01", True, 0.94),
        (12, "cell-b-camera-01", "cell-b-pallet-position-01", True, 0.89),
        (20, "cell-a-camera-01", "cell-a-pallet-position-01", False, 1.0),
        (28, "cell-b-camera-01", "cell-b-pallet-position-01", False, 1.0),
    ]

    events: list[dict[str, Any]] = []
    for offset, source_id, subject_id, val, conf in transitions:
        event_time = base_t + timedelta(seconds=offset)
        iso_str = event_time.isoformat().replace("+00:00", "Z")
        evt = {
            "schemaVersion": "1.0",
            "eventId": f"{subject_id}-{offset:02d}-{uuid.uuid4().hex[:6]}",
            "eventType": "ProcessEvent",
            "sourceId": source_id,
            "subjectId": subject_id,
            "observationType": "PalletPresent",
            "value": val,
            "unit": "boolean",
            "confidence": conf,
            "capturedAt": iso_str,
            "producedAt": iso_str,
            "publishedAt": iso_str,
            "provider": "local-replay",
            "model": "yolo26n-pallet",
            "source": "rtsp",
            "plantName": plant_name,
            "plantId": plant_id,
        }
        events.append(evt)
    return events


def run_simulation(
    sink_type: str = "local",
    output_path: str | Path = "detections.jsonl",
    interval_seconds: float = 2.0,
    iterations: int = 1,
    dry_run: bool = True,
) -> int:
    """Execute scenario simulation, streaming events at configured intervals."""
    local_sink = LocalJsonlSink(path=output_path) if sink_type in ("local", "both") else None
    fabric_sink = FabricEventstreamSink(dry_run=dry_run, fallback_jsonl_path=output_path) if sink_type in ("fabric", "both") else None

    total_published = 0
    for iteration in range(1, iterations + 1):
        logger.info("Starting simulation iteration %d/%d", iteration, iterations)
        events = generate_scenario_events()

        for event in events:
            validate_process_event(event)

            if local_sink:
                local_sink.publish(event)
            if fabric_sink:
                fabric_sink.publish(event)

            total_published += 1
            print(
                f"[{datetime.now(UTC).strftime('%H:%M:%S')}] "
                f"Published Event: {event['eventId']} | Subject: {event['subjectId']} | "
                f"Value: {event['value']} | Conf: {event['confidence']}"
            )
            if interval_seconds > 0:
                time.sleep(interval_seconds)

    if fabric_sink:
        fabric_sink.close()

    return total_published


def create_parser() -> argparse.ArgumentParser:
    """Create command-line parser."""
    parser = argparse.ArgumentParser(
        description="Replay deterministic factory events to local sinks or Microsoft Fabric."
    )
    parser.add_argument(
        "--sink",
        choices=["local", "fabric", "both"],
        default="both",
        help="Destination sink for generated events.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("simulation-events.jsonl"),
        help="Output path for local JSONL output.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Delay in seconds between emitted transition events.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of scenario cycles to run.",
    )
    parser.add_argument(
        "--live-fabric",
        action="store_true",
        help="Send to real Microsoft Fabric Eventstream (requires env var configuration).",
    )
    return parser


def main() -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = create_parser().parse_args()
    published = run_simulation(
        sink_type=args.sink,
        output_path=args.output,
        interval_seconds=args.interval,
        iterations=args.iterations,
        dry_run=not args.live_fabric,
    )
    print(f"Simulation completed. Total events published: {published}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
