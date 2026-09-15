"""Interface every perception workload implements.

Keeping this narrow is what lets the Foundry Local and Foundry cloud runtimes be
swapped without touching the mapper or the twin connector.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from tiger_poc.capture import Frame
from tiger_poc.perception.observation import Observation


@runtime_checkable
class PerceptionWorkload(Protocol):
    """Consumes frames and emits observations."""

    @property
    def runtime(self) -> str:
        """Identifier recorded as Observation.source, e.g. 'foundry-local'."""

    def observe(self, frame: Frame) -> list[Observation]:
        """Return zero or more observations for a single frame."""

    def reset(self) -> None:
        """Clear any accumulated state between runs."""
