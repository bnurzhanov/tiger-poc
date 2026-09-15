#!/usr/bin/env python3
"""Run YOLO detections against an RTSP camera and publish ProcessEvent records.

This is the first concrete producer for the sensor-agnostic perception layer. The
shared contract is designed to be reusable for non-video telemetry as the system
expands beyond CV-only observations.

Usage:
    RTSP_URL='rtsp://user:password@192.168.2.102:554/stream' \
        uv run --project apps/detect apps/detect/rtsp_yolo.py --model best.pt
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import cv2
from tiger_perception.contracts import ProcessEvent
from tiger_perception.sinks import LocalJsonlSink, validate_process_event
from ultralytics import YOLO
from ultralytics.engine.results import Results

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_ERROR = 2
APP_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = APP_DIR / "yolo26n.pt"
DEFAULT_OUTPUT = APP_DIR / "detections.jsonl"
DEFAULT_RTSP_URL = (
    "rtsp://localhost:554/cam/realmonitor?channel=1&subtype=0"
)

logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Detect objects in an RTSP stream and write JSON Lines output."
    )
    parser.add_argument(
        "--rtsp-url",
        default=os.environ.get("RTSP_URL", DEFAULT_RTSP_URL),
        help="RTSP URL. Defaults to RTSP_URL or rtsp://192.168.2.102:554.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("YOLO_MODEL", str(DEFAULT_MODEL)),
        help="YOLO model name or path to custom weights.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="JSON Lines output path.",
    )
    parser.add_argument("--camera-id", default="camera-192-168-2-102")
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument(
        "--frame-stride",
        type=int,
        default=5,
        help="Run inference on every Nth frame.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Stop after this many detections; 0 runs until interrupted.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def configure_logging(verbose: bool) -> None:
    """Configure console logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def validate_arguments(args: argparse.Namespace) -> None:
    """Validate command-line argument values."""
    if not 0.0 <= args.confidence <= 1.0:
        raise ValueError("--confidence must be between 0 and 1")
    if args.frame_stride < 1:
        raise ValueError("--frame-stride must be at least 1")
    if args.max_frames < 0:
        raise ValueError("--max-frames cannot be negative")


def extract_detections(result: Results) -> list[dict[str, object]]:
    """Convert YOLO bounding boxes into JSON-compatible dictionaries."""
    if result.boxes is None:
        return []

    coordinates = result.boxes.xyxy.cpu().tolist()
    confidences = result.boxes.conf.cpu().tolist()
    class_ids = result.boxes.cls.int().cpu().tolist()

    detections: list[dict[str, object]] = []
    for box, confidence, class_id in zip(
        coordinates, confidences, class_ids, strict=True
    ):
        detections.append(
            {
                "classId": class_id,
                "label": result.names[class_id],
                "confidence": round(confidence, 4),
                "boundingBox": {
                    "xMin": round(box[0], 2),
                    "yMin": round(box[1], 2),
                    "xMax": round(box[2], 2),
                    "yMax": round(box[3], 2),
                },
            }
        )
    return detections


def build_process_event(
    *,
    camera_id: str,
    frame_number: int,
    timestamp: str,
    detections: list[dict[str, object]],
    model_name: str,
    event_id: str | None = None,
    source_id: str | None = None,
) -> dict[str, object]:
    """Construct a schema-valid ProcessEvent for a single detection frame."""
    observation = {
        "cameraId": camera_id,
        "frameNumber": frame_number,
        "detections": detections,
    }
    event_timestamp = timestamp or datetime.now(UTC).isoformat()
    event = ProcessEvent(
        event_id=event_id or f"{camera_id}-frame-{frame_number}",
        source_id=source_id or camera_id,
        subject_id=f"frame-{frame_number}",
        observation_type="object-detections",
        value=len(detections),
        unit="detections",
        confidence=1.0 if detections else 0.0,
        captured_at=event_timestamp,
        produced_at=event_timestamp,
        published_at=event_timestamp,
        provider="camera-stream",
        model=model_name,
        source="rtsp-yolo",
        observation=observation,
    )
    return validate_process_event(event)


def run(args: argparse.Namespace) -> int:
    """Read the RTSP stream, run inference, and write detection records."""
    validate_arguments(args)
    model = YOLO(args.model)
    capture = cv2.VideoCapture(args.rtsp_url)
    if not capture.isOpened():
        capture.release()
        raise ConnectionError(
            "Could not open the RTSP stream. Check its path, credentials, and port."
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sink = LocalJsonlSink(path=args.output, max_retries=3)
    frame_number = 0
    processed_frames = 0
    logger.info("Reading camera %s; writing detections to %s", args.camera_id, args.output)

    try:
        while args.max_frames == 0 or processed_frames < args.max_frames:
            success, frame = capture.read()
            if not success:
                raise ConnectionError("The RTSP stream stopped returning frames")

            frame_number += 1
            if frame_number % args.frame_stride != 0:
                continue

            result = model.predict(
                source=frame,
                conf=args.confidence,
                verbose=False,
            )[0]
            detections = extract_detections(result)
            record = build_process_event(
                camera_id=args.camera_id,
                frame_number=frame_number,
                timestamp=datetime.now(UTC).isoformat(),
                detections=detections,
                model_name=str(model.ckpt_path) if hasattr(model, "ckpt_path") else args.model,
            )
            sink.publish(record)
            processed_frames += 1
            logger.info(
                "Frame %d: %d detection(s)",
                frame_number,
                len(detections),
            )
    finally:
        capture.release()

    return EXIT_SUCCESS


def main() -> int:
    """Run the detector and map failures to process exit codes."""
    if any(argument == "--manifest" or argument.startswith("--manifest=") for argument in sys.argv[1:]):
        from tiger_perception.runner import main as run_workload

        return run_workload()
    args = create_parser().parse_args()
    configure_logging(args.verbose)
    try:
        return run(args)
    except ValueError as error:
        logger.error("Invalid configuration: %s", error)
        return EXIT_ERROR
    except KeyboardInterrupt:
        logger.info("Stopped by user")
        return 130
    except (ConnectionError, OSError, RuntimeError) as error:
        logger.error("Detection failed: %s", error)
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())