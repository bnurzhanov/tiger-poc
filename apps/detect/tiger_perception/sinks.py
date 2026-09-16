from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .contracts import ProcessEvent

REQUIRED_FIELDS = (
    "schemaVersion",
    "eventId",
    "eventType",
    "sourceId",
    "subjectId",
    "observationType",
    "value",
    "unit",
    "confidence",
    "capturedAt",
    "producedAt",
    "publishedAt",
    "provider",
    "model",
    "source",
)

SENSITIVE_KEYS = {"token", "password", "secret", "apikey", "key", "authorization",
                  "uri", "url", "endpoint", "connectionstring"}
SCHEMA = json.loads((Path(__file__).parent / "schemas/process-event-v1.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


class SinkError(ValueError):
    """Raised when a ProcessEvent record is invalid or cannot be persisted."""


class SinkUnavailableError(SinkError):
    """Raised when the sink is temporarily unavailable."""


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _redact_event(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    if isinstance(value, str):
        return "[REDACTED]" if value.lower() in {"password", "secret", "token"} or "://" in value else value
    return value


def _sanitize_text(value: str, event: Mapping[str, Any] | None = None) -> str:
    if event is None:
        return value
    redact_target = json.dumps(event, sort_keys=True)
    for key, item in event.items():
        if isinstance(item, Mapping):
            nested = json.dumps(item, sort_keys=True)
            if key.lower() in SENSITIVE_KEYS or any(part.lower() in SENSITIVE_KEYS for part in item):
                return value.replace(nested, "[REDACTED]")
        if isinstance(item, str) and key.lower() in SENSITIVE_KEYS:
            return value.replace(item, "[REDACTED]")
    return value.replace(redact_target, "[REDACTED]")


def _redact_event(event: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in event.items():
        lower_key = str(key).lower()
        if lower_key in SENSITIVE_KEYS:
            sanitized[key] = "[REDACTED]"
            continue
        sanitized[key] = _redact_value(value)
    return sanitized


def _is_json_scalar(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _validate_timestamp(field: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SinkError(f"{field} must be a non-empty timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SinkError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise SinkError(f"{field} must include a timezone")


def validate_process_event(event: Mapping[str, Any] | ProcessEvent) -> dict[str, Any]:
    """Validate a ProcessEvent payload before publication.

    Args:
        event: Candidate ProcessEvent dictionary or typed ProcessEvent.

    Returns:
        The sanitized, JSON-safe event payload.

    Raises:
        SinkError: If the record is missing required fields or is structurally invalid.
    """
    if isinstance(event, ProcessEvent):
        event = event.to_dict()
    if not isinstance(event, Mapping):
        raise SinkError("ProcessEvent must be a JSON object")

    missing = [field for field in REQUIRED_FIELDS if field not in event]
    if missing:
        raise SinkError(f"Missing required ProcessEvent fields: {', '.join(missing)}")

    if str(event["eventType"]) != "ProcessEvent":
        raise SinkError("eventType must be 'ProcessEvent'")

    schema_version = str(event["schemaVersion"])
    if not schema_version.startswith("1"):
        raise SinkError("schemaVersion must start with '1'")

    for field in ("eventId", "sourceId", "subjectId", "observationType", "unit", "provider", "model", "source"):
        value = event[field]
        if not isinstance(value, str) or not value.strip():
            raise SinkError(f"{field} must be a non-empty string")

    confidence = event["confidence"]
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(float(confidence))
        or not 0.0 <= float(confidence) <= 1.0
    ):
        raise SinkError("confidence must be a number between 0.0 and 1.0")

    for field in ("capturedAt", "producedAt", "publishedAt"):
        _validate_timestamp(field, event[field])

    if not _is_json_scalar(event["value"]):
        raise SinkError("value must be a JSON scalar")

    sanitized = _redact_event(dict(event))
    try:
        json.dumps(sanitized, allow_nan=False)
    except (TypeError, ValueError):
        raise SinkError("ProcessEvent must contain only JSON-serializable values") from None

    error = next(VALIDATOR.iter_errors(sanitized), None)
    if error is not None:
        field = ".".join(map(str, error.absolute_path)) or "record"
        raise SinkError(f"ProcessEvent schema validation failed at {field}")
    if (sanitized["observationType"] in {"PalletPresent", "ObjectPresent"}
            and (type(sanitized["value"]) is not bool or sanitized["unit"] != "boolean")):
        raise SinkError("Presence value must be boolean with unit 'boolean'")
    return sanitized


class LocalJsonlSink:
    """Write schema-valid ProcessEvent records to a local JSONL file.

    Duplicate event IDs are treated as deterministic idempotent writes and return False
    without emitting a second line. Failed writes increment the failure counters and raise
    when the sink is unavailable or a record cannot be persisted.
    """

    def __init__(self, *, path: str | os.PathLike[str], max_retries: int = 3) -> None:
        self.path = Path(path)
        self.max_retries = max(1, max_retries)
        self.attempted_count = 0
        self.published_count = 0
        self.failed_count = 0
        self.duplicate_count = 0
        self.last_successful_publication: str | None = None
        self._healthy = True
        self._seen_event_ids: set[str] = set()

    def set_healthy(self, healthy: bool) -> None:
        self._healthy = bool(healthy)

    def _write_line(self, serialized_event: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(serialized_event)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def publish(self, event: Mapping[str, Any] | ProcessEvent) -> bool:
        """Publish a ProcessEvent to the local JSONL sink.

        Returns:
            True for a newly written event, False for a duplicate event ID.

        Raises:
            SinkUnavailableError: When the sink is unavailable or the retry budget is exhausted.
            SinkError: When the event schema is invalid.
        """
        self.attempted_count += 1
        try:
            sanitized_event = validate_process_event(event)
        except SinkError:
            self.failed_count += 1
            raise

        event_id = str(sanitized_event["eventId"])
        if event_id in self._seen_event_ids:
            self.duplicate_count += 1
            return False

        if not self._healthy:
            self.failed_count += 1
            raise SinkUnavailableError(
                "Local JSONL sink is unavailable; retry budget exhausted before publication."
            )

        for attempt in range(self.max_retries):
            try:
                self._write_line(json.dumps(sanitized_event, separators=(",", ":"), sort_keys=True))
                self._seen_event_ids.add(event_id)
                self.published_count += 1
                self.last_successful_publication = datetime.now(UTC).isoformat()
                return True
            except OSError:
                self.failed_count += 1
                if not self._healthy or attempt + 1 == self.max_retries:
                    raise SinkUnavailableError(
                        "Local JSONL write failed; retry budget exhausted. Check disk access and space."
                    ) from None

        self.failed_count += 1
        raise SinkUnavailableError(
            f"Local JSONL sink retry budget exhausted for event {event_id}."
        )


__all__ = [
    "LocalJsonlSink",
    "SinkError",
    "SinkUnavailableError",
    "validate_process_event",
]
