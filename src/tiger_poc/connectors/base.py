"""Digital-twin connector boundary.

Only implementations of this protocol should know the target platform's API or
message format. Everything upstream deals in ProcessEvent.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from tiger_poc.ontology import ProcessEvent


@runtime_checkable
class TwinConnector(Protocol):
    """Publishes process events to a destination."""

    @property
    def destination(self) -> str:
        """Human-readable target identifier used in logs."""

    def publish(self, event: ProcessEvent) -> None:
        """Send one event to the destination."""

    def close(self) -> None:
        """Flush and release any resources."""
