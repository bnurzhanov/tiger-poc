"""RTSP capture adapter for Tapo IP cameras.

Emits timestamped frames and hides stream/reconnect details from the
perception workload, per the capture adapter boundary in docs/mvp-design.md.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import TracebackType
from urllib.parse import quote

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Tapo exposes a high- and low-resolution substream on its RTSP server.
STREAM_PATHS: dict[str, str] = {"hd": "stream1", "sd": "stream2"}

DEFAULT_RTSP_PORT = 554


class CameraConnectionError(RuntimeError):
    """Raised when the RTSP stream cannot be opened or recovered."""


@dataclass(frozen=True)
class Frame:
    """A single decoded frame with capture metadata."""

    image: np.ndarray
    timestamp: datetime
    sequence: int
    source: str


@dataclass(frozen=True)
class CameraConfig:
    """Connection settings for a Tapo RTSP stream."""

    host: str
    username: str = field(repr=False)
    password: str = field(repr=False)
    port: int = DEFAULT_RTSP_PORT
    quality: str = "hd"
    open_timeout_ms: int = 10_000
    read_timeout_ms: int = 10_000

    def __post_init__(self) -> None:
        if self.quality not in STREAM_PATHS:
            valid = ", ".join(sorted(STREAM_PATHS))
            raise ValueError(f"quality must be one of: {valid}")
        if not self.host:
            raise ValueError("host is required")
        if not self.username or not self.password:
            raise ValueError("username and password are required")

    @classmethod
    def from_env(cls, host: str | None = None, quality: str = "hd") -> "CameraConfig":
        """Build a config from TAPO_* environment variables.

        Credentials are the *camera account* created in the Tapo app under
        Device Settings > Advanced Settings > Camera Account, not the cloud login.
        """
        resolved_host = host or os.environ.get("TAPO_HOST", "")
        username = os.environ.get("TAPO_USERNAME", "")
        password = os.environ.get("TAPO_PASSWORD", "")
        if not resolved_host:
            raise ValueError("Set TAPO_HOST or pass host explicitly")
        if not username or not password:
            raise ValueError("Set TAPO_USERNAME and TAPO_PASSWORD")
        return cls(
            host=resolved_host,
            username=username,
            password=password,
            port=int(os.environ.get("TAPO_RTSP_PORT", DEFAULT_RTSP_PORT)),
            quality=quality,
        )

    @property
    def rtsp_url(self) -> str:
        """Full RTSP URL including credentials. Never log this value."""
        user = quote(self.username, safe="")
        secret = quote(self.password, safe="")
        path = STREAM_PATHS[self.quality]
        return f"rtsp://{user}:{secret}@{self.host}:{self.port}/{path}"

    @property
    def safe_url(self) -> str:
        """Credential-free URL that is safe to log."""
        return f"rtsp://{self.host}:{self.port}/{STREAM_PATHS[self.quality]}"


class RtspCamera:
    """Reads frames from a Tapo RTSP stream with automatic reconnect."""

    def __init__(
        self,
        config: CameraConfig,
        *,
        max_reconnect_attempts: int = 5,
        reconnect_backoff_s: float = 2.0,
    ) -> None:
        self._config = config
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_backoff_s = reconnect_backoff_s
        self._capture: cv2.VideoCapture | None = None
        self._sequence = 0

    def __enter__(self) -> "RtspCamera":
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def is_open(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    def open(self) -> None:
        """Open the stream, forcing TCP transport for reliable decoding."""
        if self.is_open:
            return

        # FFmpeg options must be set before VideoCapture construction.
        # nobuffer/low_delay keep the decoder near the live edge.
        os.environ.setdefault(
            "OPENCV_FFMPEG_CAPTURE_OPTIONS",
            "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay"
            f"|stimeout;{self._config.open_timeout_ms * 1000}",
        )

        logger.info("Connecting to %s", self._config.safe_url)
        capture = cv2.VideoCapture(self._config.rtsp_url, cv2.CAP_FFMPEG)
        capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self._config.open_timeout_ms)
        capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self._config.read_timeout_ms)
        # Keep latency low by not buffering stale frames.
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not capture.isOpened():
            capture.release()
            raise CameraConnectionError(
                f"Could not open {self._config.safe_url}. "
                "Check the camera account credentials and that RTSP is enabled."
            )

        self._capture = capture
        logger.info("Connected to %s", self._config.safe_url)

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
            logger.info("Disconnected from %s", self._config.safe_url)

    def read(self) -> Frame | None:
        """Read one frame, or None if the stream returned no data."""
        if self._capture is None:
            raise CameraConnectionError("Camera is not open; call open() first")

        ok, image = self._capture.read()
        if not ok or image is None:
            return None

        self._sequence += 1
        return Frame(
            image=image,
            timestamp=datetime.now(timezone.utc),
            sequence=self._sequence,
            source=self._config.safe_url,
        )

    def flush(self, *, max_frames: int = 300, live_threshold_s: float = 0.015) -> int:
        """Discard queued frames so the next read reflects the current view.

        FFmpeg queues frames regardless of CAP_PROP_BUFFERSIZE, so after any
        pause the decoder holds stale imagery. Buffered frames return
        instantly; once a grab blocks on the network we are at the live edge.
        """
        if self._capture is None:
            raise CameraConnectionError("Camera is not open; call open() first")

        dropped = 0
        while dropped < max_frames:
            started = time.monotonic()
            if not self._capture.grab():
                break
            if time.monotonic() - started > live_threshold_s:
                break
            dropped += 1

        if dropped:
            logger.debug("Discarded %d stale frames", dropped)
        return dropped

    def read_latest(self) -> Frame | None:
        """Read the most current frame, skipping any backlog."""
        self.flush()
        return self.read()

    def _reconnect(self) -> None:
        """Reopen the stream with linear backoff."""
        self.close()
        for attempt in range(1, self._max_reconnect_attempts + 1):
            delay = self._reconnect_backoff_s * attempt
            logger.warning(
                "Reconnect attempt %d/%d in %.1fs",
                attempt,
                self._max_reconnect_attempts,
                delay,
            )
            time.sleep(delay)
            try:
                self.open()
                return
            except CameraConnectionError:
                logger.warning("Reconnect attempt %d failed", attempt)
        raise CameraConnectionError(
            f"Lost connection to {self._config.safe_url} and could not recover"
        )

    def iter_frames(
        self,
        *,
        max_frames: int | None = None,
        target_fps: float | None = None,
    ) -> Iterator[Frame]:
        """Yield frames until max_frames is reached or the caller stops.

        Set target_fps to sample the stream instead of decoding every frame.
        Sampled frames are taken from the live edge, so a slow consumer falls
        behind in frame count rather than in wall-clock time.
        """
        self.open()
        min_interval_s = 1.0 / target_fps if target_fps else 0.0
        emitted = 0
        next_sample = time.monotonic() + min_interval_s

        while max_frames is None or emitted < max_frames:
            if min_interval_s:
                delay = next_sample - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                self.flush()

            frame = self.read()
            if frame is None:
                self._reconnect()
                continue

            if min_interval_s:
                # Advance on a fixed grid so flush and decode time do not
                # stretch the interval; resync if a slow consumer fell behind.
                next_sample += min_interval_s
                if next_sample < time.monotonic():
                    next_sample = time.monotonic() + min_interval_s

            emitted += 1
            yield frame
