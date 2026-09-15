"""Local sink connector.

Records the exact payload that would be sent to the twin platform, so the demo
path stays runnable when the real platform is not reachable.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import TracebackType

from tiger_poc.ontology import ProcessEvent

logger = logging.getLogger(__name__)


class LocalSinkConnector:
    """Writes events as JSON Lines and mirrors them to the log."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path else None
        self._handle = None
        self._published = 0

        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self._path.open("a", encoding="utf-8")

    def __enter__(self) -> "LocalSinkConnector":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def destination(self) -> str:
        return str(self._path) if self._path else "local-sink://stdout"

    @property
    def published(self) -> int:
        return self._published

    def publish(self, event: ProcessEvent) -> None:
        payload = json.dumps(event.to_dict())
        logger.info("-> %s %s", self.destination, payload)

        if self._handle is not None:
            self._handle.write(payload + "\n")
            self._handle.flush()

        self._published += 1

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None
