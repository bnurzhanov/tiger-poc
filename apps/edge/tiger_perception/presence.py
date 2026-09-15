"""Stateful presence evaluation rule with confirmation windows and transition tracking."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .contracts import ProcessEvent, RawDetection


@dataclass
class RegionConfig:
    """Bounding region configuration for a pallet position."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def contains_point(self, x: float, y: float) -> bool:
        """Check whether a point is within the bounding box."""
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max

    def intersects(self, bbox: dict[str, float], min_overlap: float = 0.3) -> bool:
        """Check if detection bbox overlaps with this region by at least min_overlap IoU or intersection ratio."""
        bx_min = bbox.get("x_min", 0.0)
        by_min = bbox.get("y_min", 0.0)
        bx_max = bbox.get("x_max", 1.0)
        by_max = bbox.get("y_max", 1.0)

        inter_xmin = max(self.x_min, bx_min)
        inter_ymin = max(self.y_min, by_min)
        inter_xmax = min(self.x_max, bx_max)
        inter_ymax = min(self.y_max, by_max)

        if inter_xmax <= inter_xmin or inter_ymax <= inter_ymin:
            return False

        inter_area = (inter_xmax - inter_xmin) * (inter_ymax - inter_ymin)
        region_area = (self.x_max - self.x_min) * (self.y_max - self.y_min)
        if region_area <= 0:
            return False

        return (inter_area / region_area) >= min_overlap


@dataclass
class PresenceRuleConfig:
    """Configuration parameters for the region presence rule."""

    source_id: str
    subject_id: str
    region: RegionConfig
    target_class: str = "pallet"
    confidence_threshold: float = 0.5
    occupied_confirmation_frames: int = 3
    empty_confirmation_frames: int = 5
    provider: str = "local-yolo"
    model: str = "pallet-detector-v1"
    source: str = "rtsp"
    plant_name: str | None = None
    plant_id: str | None = None


class RegionPresenceRule:
    """Stateful presence detector that confirms state over a temporal window and suppresses duplicate events."""

    def __init__(self, config: PresenceRuleConfig) -> None:
        self.config = config
        self.confirmed_present: bool | None = None  # None indicates initial unconfirmed/unknown state
        self.consecutive_occupied_count: int = 0
        self.consecutive_empty_count: int = 0
        self.is_available: bool = False

    def process_frame_detections(
        self,
        detections: list[RawDetection] | list[dict[str, Any]],
        captured_at: str,
        *,
        is_usable: bool = True,
    ) -> ProcessEvent | None:
        """Evaluate a frame's detections and return a ProcessEvent on confirmed transition."""
        if not is_usable:
            # Stale or unusable frame: reset pending counts, keep confirmed state intact
            self.consecutive_occupied_count = 0
            self.consecutive_empty_count = 0
            self.is_available = False
            return None

        self.is_available = True

        qualifying_detection: Any | None = None
        max_confidence = 0.0

        for det in detections:
            label = det.label if isinstance(det, RawDetection) else det.get("label", "")
            conf = det.confidence if isinstance(det, RawDetection) else float(det.get("confidence", 0.0))
            bbox = det.bounding_box if isinstance(det, RawDetection) else det.get("bounding_box", {})

            if label.lower() == self.config.target_class.lower() and conf >= self.config.confidence_threshold:
                if self.config.region.intersects(bbox):
                    if conf > max_confidence:
                        max_confidence = conf
                        qualifying_detection = det

        now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        if qualifying_detection is not None:
            self.consecutive_occupied_count += 1
            self.consecutive_empty_count = 0

            if self.consecutive_occupied_count >= self.config.occupied_confirmation_frames:
                if self.confirmed_present is not True:
                    # Confirmed transition to Occupied
                    self.confirmed_present = True
                    event_id = f"{self.config.subject_id}-{uuid.uuid4().hex[:8]}"
                    return ProcessEvent(
                        event_id=event_id,
                        source_id=self.config.source_id,
                        subject_id=self.config.subject_id,
                        observation_type="PalletPresent",
                        value=True,
                        unit="boolean",
                        confidence=round(max_confidence, 2),
                        captured_at=captured_at,
                        produced_at=now_iso,
                        published_at=now_iso,
                        provider=self.config.provider,
                        model=self.config.model,
                        source=self.config.source,
                        plant_name=self.config.plant_name,
                        plant_id=self.config.plant_id,
                    )
        else:
            self.consecutive_empty_count += 1
            self.consecutive_occupied_count = 0

            if self.consecutive_empty_count >= self.config.empty_confirmation_frames:
                if self.confirmed_present is not False:
                    # Confirmed transition to Empty
                    self.confirmed_present = False
                    event_id = f"{self.config.subject_id}-{uuid.uuid4().hex[:8]}"
                    return ProcessEvent(
                        event_id=event_id,
                        source_id=self.config.source_id,
                        subject_id=self.config.subject_id,
                        observation_type="PalletPresent",
                        value=False,
                        unit="boolean",
                        confidence=1.0,  # Explicit high confidence for empty confirmation after full window
                        captured_at=captured_at,
                        produced_at=now_iso,
                        published_at=now_iso,
                        provider=self.config.provider,
                        model=self.config.model,
                        source=self.config.source,
                        plant_name=self.config.plant_name,
                        plant_id=self.config.plant_id,
                    )

        return None
