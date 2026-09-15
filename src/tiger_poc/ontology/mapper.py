"""Maps observations onto a narrow line-monitoring vocabulary.

Emits an event only when a state change is confirmed across several
observations, so a flickering perception signal cannot produce an event storm.
"""

from __future__ import annotations

import logging

from tiger_poc.ontology.event import ProcessEvent
from tiger_poc.perception import Observation

logger = logging.getLogger(__name__)

# Vocabulary for the line-monitoring-v1 ontology.
DEFAULT_STATE_MAP: dict[str, str] = {"active": "running", "idle": "idle"}


class LineMonitoringMapper:
    """Turns activity observations into debounced ProcessStateChanged events."""

    ontology = "line-monitoring-v1"
    event_type = "ProcessStateChanged"

    def __init__(
        self,
        *,
        observation_type: str = "activity",
        state_map: dict[str, str] | None = None,
        min_confidence: float = 0.6,
        consecutive_for: int = 2,
    ) -> None:
        if consecutive_for < 1:
            raise ValueError("consecutive_for must be at least 1")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")

        self._observation_type = observation_type
        self._state_map = dict(state_map or DEFAULT_STATE_MAP)
        self._min_confidence = min_confidence
        self._consecutive_for = consecutive_for
        self._current_state: str | None = None
        self._candidate: str | None = None
        self._streak: list[Observation] = []

    @property
    def current_state(self) -> str | None:
        """Last committed state, or None before the first event."""
        return self._current_state

    def reset(self) -> None:
        self._current_state = None
        self._candidate = None
        self._streak = []

    def map(self, observations: list[Observation]) -> list[ProcessEvent]:
        """Return events for any state changes confirmed by these observations."""
        events: list[ProcessEvent] = []

        for observation in observations:
            if observation.observation_type != self._observation_type:
                continue
            if observation.confidence < self._min_confidence:
                logger.debug(
                    "Ignoring low-confidence observation (%.2f)", observation.confidence
                )
                continue

            state = self._state_map.get(str(observation.value))
            if state is None:
                logger.warning(
                    "No ontology mapping for value %r; ignoring", observation.value
                )
                continue

            event = self._advance(state, observation)
            if event is not None:
                events.append(event)

        return events

    def _advance(self, state: str, observation: Observation) -> ProcessEvent | None:
        """Track the streak and commit once the change is confirmed."""
        if state == self._current_state:
            self._candidate = None
            self._streak = []
            return None

        if state != self._candidate:
            self._candidate = state
            self._streak = []

        self._streak.append(observation)
        if len(self._streak) < self._consecutive_for:
            return None

        # Averaging across the streak keeps a single strong frame from
        # overstating confidence in the committed transition.
        confidence = sum(o.confidence for o in self._streak) / len(self._streak)

        self._current_state = state
        self._candidate = None
        self._streak = []

        return ProcessEvent(
            event_type=self.event_type,
            subject_id=observation.subject_id,
            state=state,
            timestamp=observation.timestamp,
            confidence=confidence,
            source=observation.source,
        )
