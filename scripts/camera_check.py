"""CLI smoke test: verify RTSP streaming and ONVIF control against a Tapo camera.

Usage:
    export TAPO_USERNAME=... TAPO_PASSWORD=...
    python scripts/camera_check.py --host 10.0.0.12 --frames 30 --save-frame out.jpg
"""

from __future__ import annotations

import argparse
import logging
import sys

import cv2

from tiger_poc.capture import CameraConfig, CameraConnectionError, RtspCamera
from tiger_poc.capture.image_correction import reduce_window_glare

logger = logging.getLogger("camera_check")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=None, help="Defaults to TAPO_HOST")
    parser.add_argument("--quality", choices=("hd", "sd"), default="hd")
    parser.add_argument("--frames", type=int, default=30, help="Frames to read")
    parser.add_argument("--target-fps", type=float, default=None)
    parser.add_argument("--save-frame", help="Write the last frame to this path")
    parser.add_argument(
        "--deglare",
        action="store_true",
        help="Reduce broad window glare in the saved frame",
    )
    parser.add_argument("--onvif", action="store_true", help="Also query ONVIF info")
    return parser.parse_args()


def check_onvif(config: CameraConfig) -> None:
    """Report device identity and the camera-advertised stream URI."""
    from tiger_poc.capture.tapo_onvif import TapoOnvifClient

    with TapoOnvifClient(config.host, config.username, config.password) as client:
        info = client.device_info()
        logger.info("Device: %s %s", info.manufacturer, info.model)
        logger.info("Firmware: %s", info.firmware_version)
        # Contains credentials in some firmwares, so log only the path portion.
        logger.info("Stream path: %s", client.stream_uri().split("@")[-1])


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()

    try:
        config = CameraConfig.from_env(host=args.host, quality=args.quality)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    if args.onvif:
        try:
            check_onvif(config)
        except Exception as exc:  # ONVIF support varies widely across Tapo models
            logger.warning("ONVIF check failed: %s", exc)

    last_frame = None
    try:
        with RtspCamera(config) as camera:
            for frame in camera.iter_frames(
                max_frames=args.frames, target_fps=args.target_fps
            ):
                last_frame = frame
                height, width = frame.image.shape[:2]
                logger.info(
                    "frame %d %dx%d at %s",
                    frame.sequence,
                    width,
                    height,
                    frame.timestamp.isoformat(),
                )
    except CameraConnectionError as exc:
        logger.error("%s", exc)
        return 1

    if last_frame is None:
        logger.error("No frames received from %s", config.safe_url)
        return 1

    if args.save_frame:
        image = reduce_window_glare(last_frame.image) if args.deglare else last_frame.image
        cv2.imwrite(args.save_frame, image)
        logger.info("Wrote %s", args.save_frame)

    logger.info("OK: read %d frames from %s", last_frame.sequence, config.safe_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
