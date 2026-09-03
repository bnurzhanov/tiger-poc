"""The observation contract emitted by every perception workload.

Field names follow docs/mvp-design.md so the ontology mapper stays independent
of which workload or inference runtime produced the data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Observation:
    """A single measurement about a subject at a point in time."""

    subject_id: str
    observation_type: str
    value: Any
    timestamp: datetime
    confidence: float
    source: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not self.subject_id:
            raise ValueError("subject_id is required")
        if not self.observation_type:
            raise ValueError("observation_type is required")

    def to_dict(self) -> dict[str, Any]:
        """Serialize using the camelCase keys the twin connector expects."""
        return {
            "subjectId": self.subject_id,
            "observationType": self.observation_type,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "confidence": round(self.confidence, 4),
            "source": self.source,
        }
