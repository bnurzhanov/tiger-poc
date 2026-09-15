"""Motion-based perception workload.

Uses running-average background subtraction so the pipeline produces real
observations before any model is wired up. Swap this for a Foundry Local or
Foundry cloud workload without changing the Observation contract.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from tiger_poc.capture import Frame
from tiger_poc.perception.observation import Observation

logger = logging.getLogger(__name__)


class MotionWorkload:
    """Emits a motion ratio and a coarse activity state for each frame."""

    def __init__(
        self,
        subject_id: str,
        *,
        min_area_ratio: float = 0.002,
        pixel_threshold: int = 25,
        background_alpha: float = 0.05,
        warmup_frames: int = 10,
        working_width: int = 640,
        runtime: str = "mock-motion",
    ) -> None:
        if not 0.0 < min_area_ratio < 1.0:
            raise ValueError("min_area_ratio must be between 0.0 and 1.0")
        if not 0.0 < background_alpha <= 1.0:
            raise ValueError("background_alpha must be between 0.0 and 1.0")

        self._subject_id = subject_id
        self._min_area_ratio = min_area_ratio
        self._pixel_threshold = pixel_threshold
        self._background_alpha = background_alpha
        self._warmup_frames = warmup_frames
        self._working_width = working_width
        self._runtime = runtime
        self._background: np.ndarray | None = None
        self._frames_seen = 0

    @property
    def runtime(self) -> str:
        return self._runtime

    def reset(self) -> None:
        self._background = None
        self._frames_seen = 0

    def _prepare(self, image: np.ndarray) -> np.ndarray:
        """Downscale, grayscale, and blur to suppress sensor noise."""
        height, width = image.shape[:2]
        if width > self._working_width:
            scale = self._working_width / width
            image = cv2.resize(image, (self._working_width, int(height * scale)))
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (21, 21), 0)

    def observe(self, frame: Frame) -> list[Observation]:
        """Return motion observations, or an empty list during warmup."""
        gray = self._prepare(frame.image)
        self._frames_seen += 1

        if self._background is None:
            self._background = gray.astype(np.float32)
            return []

        delta = cv2.absdiff(gray, cv2.convertScaleAbs(self._background))
        _, mask = cv2.threshold(
            delta, self._pixel_threshold, 255, cv2.THRESH_BINARY
        )
        mask = cv2.dilate(mask, None, iterations=2)
        ratio = float(np.count_nonzero(mask)) / float(mask.size)

        cv2.accumulateWeighted(
            gray.astype(np.float32), self._background, self._background_alpha
        )

        # The background model is still stabilizing, so suppress false positives.
        if self._frames_seen <= self._warmup_frames:
            return []

        active = ratio >= self._min_area_ratio
        margin = abs(ratio - self._min_area_ratio) / self._min_area_ratio
        confidence = 0.5 + 0.5 * min(1.0, margin)

        return [
            Observation(
                subject_id=self._subject_id,
                observation_type="motion_ratio",
                value=round(ratio, 5),
                timestamp=frame.timestamp,
                confidence=confidence,
                source=self._runtime,
            ),
            Observation(
                subject_id=self._subject_id,
                observation_type="activity",
                value="active" if active else "idle",
                timestamp=frame.timestamp,
                confidence=confidence,
                source=self._runtime,
            ),
        ]
