"""Process event contract emitted by the ontology mapper.

Field names match the example in docs/mvp-design.md so the twin connector stays
the only component that knows the target platform's format.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ProcessEvent:
    """A committed change in a subject's process state."""

    event_type: str
    subject_id: str
    state: str
    timestamp: datetime
    confidence: float
    source: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not self.subject_id:
            raise ValueError("subject_id is required")
        if not self.state:
            raise ValueError("state is required")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the documented event payload."""
        return {
            "eventType": self.event_type,
            "subjectId": self.subject_id,
            "state": self.state,
            "timestamp": self.timestamp.isoformat(),
            "confidence": round(self.confidence, 4),
            "source": self.source,
        }
