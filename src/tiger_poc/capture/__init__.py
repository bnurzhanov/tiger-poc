"""Capture adapters that turn camera inputs into timestamped frames."""

from tiger_poc.capture.rtsp_camera import (
    CameraConfig,
    CameraConnectionError,
    Frame,
    RtspCamera,
)

__all__ = ["CameraConfig", "CameraConnectionError", "Frame", "RtspCamera"]
