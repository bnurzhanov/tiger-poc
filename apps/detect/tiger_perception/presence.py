"""Confirm region presence from fresh, successful normalized inference evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from .contracts import Observation, RawDetection, RawInference


@dataclass(frozen=True)
class PresencePolicy:
    """Use box-center matching in an inclusive normalized xyxy rectangle.

    Occupied confidence is the minimum best-match score over the confirmation
    window. Empty confidence is zero (not estimated), not an absence probability.
    Both states require at least two distinct frames and the configured duration.
    """

    region: tuple[float, float, float, float]
    labels: tuple[str, ...] = ("pallet",)
    confidence: float = 0.5
    occupied_seconds: float = 2.0
    empty_seconds: float = 3.0
    stale_seconds: float = 2.0

    def __post_init__(self) -> None:
        if len(self.region) != 4 or not all(
            math.isfinite(value) and 0 <= value <= 1 for value in self.region
        ):
            raise ValueError("region must contain four normalized coordinates")
        left, top, right, bottom = self.region
        if left >= right or top >= bottom:
            raise ValueError("region must have positive width and height")
        if not self.labels or any(not label.strip() for label in self.labels):
            raise ValueError("at least one non-empty detection label is required")
        if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between zero and one")
        if any(not math.isfinite(value) or value < 0 for value in (
            self.occupied_seconds, self.empty_seconds, self.stale_seconds
        )) or self.stale_seconds == 0:
            raise ValueError("confirmation delays must be nonnegative; staleSeconds positive")

    def matches(self, detection: RawDetection) -> bool:
        """Return whether a qualifying box center is inside this region."""
        if detection.label not in self.labels or detection.confidence < self.confidence:
            return False
        box = detection.bounding_box
        center_x = (box["xMin"] + box["xMax"]) / 2
        center_y = (box["yMin"] + box["yMax"]) / 2
        left, top, right, bottom = self.region
        return left <= center_x <= right and top <= center_y <= bottom


class PresenceRule:
    """Own confirmation and availability for exactly one source and subject."""

    def __init__(self, *, source_id: str, subject_id: str, policy: PresencePolicy,
                 observation_type: str = "PalletPresent") -> None:
        self.source_id = source_id
        self.subject_id = subject_id
        self.policy = policy
        self.observation_type = observation_type
        self.confirmed: bool | None = None
        self.availability = "unknown"
        self.last_captured_at: datetime | None = None
        self._sequence = -1
        self._candidate: bool | None = None
        self._since: datetime | None = None
        self._frames = 0
        self._confidence = 0.0

    def unavailable(self) -> None:
        """Retain last confirmed occupancy but discard pending evidence."""
        self.availability = "unavailable"
        self._candidate = None
        self._since = None
        self._frames = 0

    def reconnect(self) -> None:
        """Accept a new capture sequence only after its explicit connection epoch."""
        self.unavailable()
        self._sequence = -1
        self.last_captured_at = None

    def expire(self, now: datetime) -> None:
        """Mark evidence unavailable if no fresh observation has arrived."""
        if self.last_captured_at is None or not (
            0 <= (now - self.last_captured_at).total_seconds() < self.policy.stale_seconds
        ):
            self.unavailable()

    def observe(self, inference: RawInference, *, now: datetime) -> Observation | None:
        """Emit initialization or a confirmed change, never an outage as empty."""
        if inference.source_id != self.source_id:
            raise ValueError("inference source does not match presence rule")
        captured = datetime.fromisoformat(inference.captured_at)
        produced = datetime.fromisoformat(inference.produced_at)
        if captured.tzinfo is None or produced.tzinfo is None or now.tzinfo is None:
            raise ValueError("evidence timestamps must include a timezone")
        if (not inference.succeeded or inference.sequence <= self._sequence
                or not 0 <= (now - captured).total_seconds() < self.policy.stale_seconds
                or not captured <= produced <= now
                or (self.last_captured_at is not None and captured <= self.last_captured_at)):
            self.unavailable()
            return None
        for detection in inference.detections:
            box = detection.bounding_box
            coordinates = [box.get(key, math.nan) for key in ("xMin", "yMin", "xMax", "yMax")]
            if (not all(math.isfinite(value) and 0 <= value <= 1 for value in coordinates)
                    or coordinates[0] >= coordinates[2] or coordinates[1] >= coordinates[3]
                    or not math.isfinite(detection.confidence)
                    or not 0 <= detection.confidence <= 1):
                self.unavailable()
                return None
        self.expire(captured)
        self.last_captured_at = captured
        self._sequence = inference.sequence
        scores = [item.confidence for item in inference.detections if self.policy.matches(item)]
        candidate = bool(scores)
        confidence = max(scores, default=0.0)
        if candidate != self._candidate:
            self._candidate = candidate
            self._since = captured
            self._frames = 0
            self._confidence = confidence
        self._frames += 1
        self._confidence = min(self._confidence, confidence)
        duration = self.policy.occupied_seconds if candidate else self.policy.empty_seconds
        assert self._since is not None
        if self._frames < 2 or (captured - self._since).total_seconds() < duration:
            self.availability = "confirming"
            return None
        self.availability = "current"
        if self.confirmed is candidate:
            return None
        self.confirmed = candidate
        return Observation(
            observation_id=str(uuid4()), source_id=self.source_id,
            subject_id=self.subject_id, subject_resolution="resolved",
            observation_type=self.observation_type, value=candidate, unit="boolean",
            confidence=self._confidence, captured_at=inference.captured_at,
            produced_at=inference.produced_at, provider=inference.provider,
            model=inference.model, raw_inference_id=inference.inference_id,
            metadata={
                "confidenceMeaning": "minimum-best-match" if candidate else "absence-not-estimated",
                "confirmationStartedAt": self._since.isoformat(),
                "confirmationFrames": self._frames,
            },
        )