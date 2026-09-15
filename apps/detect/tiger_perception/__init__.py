"""Sensor-agnostic perception contracts and local replay sinks.

This package defines the shared ProcessEvent contract for observations produced by
video streams, CV inference, and other telemetry sources. The RTSP detector is the
first concrete producer, but the contract is intentionally reusable across sensors.
"""

from .sinks import (
    LocalJsonlSink,
    SinkError,
    SinkUnavailableError,
    validate_process_event,
)

__all__ = [
    "LocalJsonlSink",
    "SinkError",
    "SinkUnavailableError",
    "validate_process_event",
]
