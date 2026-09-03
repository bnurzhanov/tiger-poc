"""Run the full pipeline: capture -> perception -> ontology -> twin connector.

Usage:
    set -a && source .env && set +a
    python scripts/run_pipeline.py --subject station-01 --seconds 30 --events out.jsonl
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from tiger_poc.capture import CameraConfig, CameraConnectionError, RtspCamera
from tiger_poc.connectors import LocalSinkConnector, TwinConnector
from tiger_poc.ontology import LineMonitoringMapper
from tiger_poc.perception import MotionWorkload, PerceptionWorkload

logger = logging.getLogger("pipeline")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=None, help="Defaults to TAPO_HOST")
    parser.add_argument("--quality", choices=("hd", "sd"), default="sd")
    parser.add_argument("--subject", default="station-01")
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--sensitivity", type=float, default=0.002)
    parser.add_argument(
        "--confirm-for",
        type=int,
        default=2,
        help="Consecutive observations required to commit a state change",
    )
    parser.add_argument("--events", help="Append published events to this JSONL file")
    return parser.parse_args()


def run(
    camera: RtspCamera,
    workload: PerceptionWorkload,
    mapper: LineMonitoringMapper,
    connector: TwinConnector,
    *,
    fps: float,
    seconds: float,
) -> tuple[int, int]:
    """Drive the pipeline for a fixed duration, returning observation/event counts."""
    deadline = time.monotonic() + seconds
    observations = 0
    events = 0

    for frame in camera.iter_frames(target_fps=fps):
        batch = workload.observe(frame)
        observations += len(batch)

        for event in mapper.map(batch):
            connector.publish(event)
            events += 1

        if time.monotonic() >= deadline:
            break

    return observations, events


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()

    try:
        config = CameraConfig.from_env(host=args.host, quality=args.quality)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    workload = MotionWorkload(args.subject, min_area_ratio=args.sensitivity)
    mapper = LineMonitoringMapper(consecutive_for=args.confirm_for)
    connector = LocalSinkConnector(args.events)

    logger.info(
        "source=%s inference=%s ontology=%s destination=%s",
        config.safe_url,
        workload.runtime,
        mapper.ontology,
        connector.destination,
    )

    try:
        with RtspCamera(config) as camera, connector:
            observations, events = run(
                camera,
                workload,
                mapper,
                connector,
                fps=args.fps,
                seconds=args.seconds,
            )
    except CameraConnectionError as exc:
        logger.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        logger.info("Stopped by user")
        return 0

    logger.info(
        "Done: %d observations -> %d events, final state=%s",
        observations,
        events,
        mapper.current_state,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
