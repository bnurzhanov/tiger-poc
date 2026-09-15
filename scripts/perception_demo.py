"""Run the capture adapter through a perception workload and print observations.

Usage:
    set -a && source .env && set +a
    python scripts/perception_demo.py --subject station-01 --seconds 20
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from tiger_poc.capture import CameraConfig, CameraConnectionError, RtspCamera
from tiger_poc.perception import MotionWorkload, PerceptionWorkload

logger = logging.getLogger("perception_demo")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=None, help="Defaults to TAPO_HOST")
    parser.add_argument("--quality", choices=("hd", "sd"), default="sd")
    parser.add_argument("--subject", default="station-01", help="Subject id")
    parser.add_argument("--fps", type=float, default=2.0, help="Sampling rate")
    parser.add_argument("--seconds", type=float, default=15.0, help="Run duration")
    parser.add_argument("--sensitivity", type=float, default=0.002)
    parser.add_argument("--jsonl", help="Append observations to this JSONL file")
    return parser.parse_args()


def run(
    camera: RtspCamera,
    workload: PerceptionWorkload,
    *,
    fps: float,
    seconds: float,
    sink=None,
) -> int:
    """Drive frames through the workload until the time budget expires."""
    deadline = time.monotonic() + seconds
    count = 0

    for frame in camera.iter_frames(target_fps=fps):
        for observation in workload.observe(frame):
            count += 1
            payload = observation.to_dict()
            logger.info(
                "%-13s %-8s conf=%.2f",
                payload["observationType"],
                payload["value"],
                payload["confidence"],
            )
            if sink is not None:
                sink.write(json.dumps(payload) + "\n")
                sink.flush()

        if time.monotonic() >= deadline:
            break

    return count


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()

    try:
        config = CameraConfig.from_env(host=args.host, quality=args.quality)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    workload = MotionWorkload(args.subject, min_area_ratio=args.sensitivity)
    sink = open(args.jsonl, "a", encoding="utf-8") if args.jsonl else None

    try:
        with RtspCamera(config) as camera:
            count = run(
                camera,
                workload,
                fps=args.fps,
                seconds=args.seconds,
                sink=sink,
            )
    except CameraConnectionError as exc:
        logger.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        logger.info("Stopped by user")
        return 0
    finally:
        if sink is not None:
            sink.close()

    logger.info("Emitted %d observations from %s", count, workload.runtime)
    return 0 if count else 1


if __name__ == "__main__":
    sys.exit(main())
