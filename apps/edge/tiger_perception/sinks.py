"""Sinks for persisting and streaming ProcessEvents to local storage and Microsoft Fabric."""

from __future__ import annotations

import json
import logging
import math
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from .contracts import ProcessEvent

logger = logging.getLogger(__name__)

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

SENSITIVE_KEYS = {"token", "password", "secret", "apiKey", "apikey", "key", "authorization"}


class SinkError(ValueError):
    """Raised when a ProcessEvent record is invalid or cannot be persisted."""


class SinkUnavailableError(SinkError):
    """Raised when the sink is temporarily unavailable."""


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _redact_value(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    if isinstance(value, str):
        return "[REDACTED]" if value.lower() in {"password", "secret", "token"} else value
    return value


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
    """Validate that a ProcessEvent adheres to the required schema and bounds."""
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

    if "sensitive" in event and isinstance(event["sensitive"], Mapping):
        redacted = _redact_event(event["sensitive"])
        if json.dumps(redacted, sort_keys=True) != json.dumps(event["sensitive"], sort_keys=True):
            event = {**event, "sensitive": redacted}

    sanitized = _redact_event(dict(event))
    return sanitized


class LocalJsonlSink:
    """Write schema-valid ProcessEvent records to a local JSONL file."""

    def __init__(self, path: str | os.PathLike[str] = "detections.jsonl", max_retries: int = 3) -> None:
        self.path = Path(path)
        self.max_retries = max(1, max_retries)
        self.attempted_count = 0
        self.published_count = 0
        self.failed_count = 0
        self.duplicate_count = 0
        self.last_successful_publication: str | None = None
        self._healthy = True
        self._seen_event_ids: set[str] = set()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def set_healthy(self, healthy: bool) -> None:
        self._healthy = bool(healthy)

    def _write_line(self, serialized_event: str) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(serialized_event)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def publish(self, event: Mapping[str, Any] | ProcessEvent) -> bool:
        """Publish a ProcessEvent to the local JSONL sink."""
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

        serialized = json.dumps(sanitized_event, sort_keys=True)
        self._write_line(serialized)
        self._seen_event_ids.add(event_id)
        self.published_count += 1
        self.last_successful_publication = sanitized_event.get("publishedAt")
        return True


class FabricEventstreamSink:
    """Publishes ProcessEvents to Microsoft Fabric Eventstream with offline dry-run fallback."""

    def __init__(
        self,
        connection_string: str | None = None,
        eventhub_name: str | None = None,
        rest_endpoint: str | None = None,
        dry_run: bool = False,
        fallback_jsonl_path: str | Path | None = None,
    ) -> None:
        self.connection_string = connection_string or os.environ.get("FABRIC_EVENTSTREAM_CONNECTION_STRING")
        self.eventhub_name = eventhub_name or os.environ.get("FABRIC_EVENTSTREAM_EVENTHUB_NAME")
        self.rest_endpoint = rest_endpoint or os.environ.get("FABRIC_EVENTSTREAM_REST_ENDPOINT")
        self.dry_run = dry_run or (os.environ.get("MOCK_FABRIC", "").lower() in {"1", "true", "yes"})

        if not self.connection_string and not self.rest_endpoint:
            self.dry_run = True

        self.fallback_jsonl = LocalJsonlSink(path=fallback_jsonl_path) if fallback_jsonl_path else None
        self._producer_client: Any = None

    def _get_eventhub_producer(self) -> Any:
        if self._producer_client is None:
            try:
                from azure.eventhub import EventHubProducerClient

                if self.eventhub_name:
                    self._producer_client = EventHubProducerClient.from_connection_string(
                        conn_str=self.connection_string,
                        eventhub_name=self.eventhub_name,
                    )
                else:
                    self._producer_client = EventHubProducerClient.from_connection_string(
                        conn_str=self.connection_string,
                    )
            except Exception as exc:
                raise SinkUnavailableError(f"Failed to initialize Azure EventHub client: {exc}") from exc
        return self._producer_client

    def publish(self, event: ProcessEvent | Mapping[str, Any]) -> bool:
        """Validate and publish event to Fabric Eventstream (or dry-run trace)."""
        validated = validate_process_event(event)

        if self.fallback_jsonl:
            self.fallback_jsonl.publish(validated)

        if self.dry_run:
            logger.info(
                "[DRY-RUN] FabricEventstreamSink published eventId=%s subjectId=%s value=%s",
                validated["eventId"],
                validated["subjectId"],
                validated["value"],
            )
            return True

        if self.connection_string:
            try:
                from azure.eventhub import EventData

                producer = self._get_eventhub_producer()
                event_data = EventData(json.dumps(validated))
                with producer:
                    batch = producer.create_batch()
                    batch.add(event_data)
                    producer.send_batch(batch)
                return True
            except Exception as exc:
                logger.error("Failed to publish event to Fabric Eventstream Event Hub: %s", exc)
                raise SinkUnavailableError(f"EventHub ingestion failed: {exc}") from exc

        if self.rest_endpoint:
            try:
                headers = {"Content-Type": "application/json"}
                response = requests.post(
                    self.rest_endpoint,
                    json=validated,
                    headers=headers,
                    timeout=5.0,
                )
                response.raise_for_status()
                return True
            except Exception as exc:
                logger.error("Failed to publish event to Fabric REST endpoint: %s", exc)
                raise SinkUnavailableError(f"REST ingestion failed: {exc}") from exc

        return True

    def close(self) -> None:
        """Clean up underlying network clients."""
        if self._producer_client is not None:
            try:
                self._producer_client.close()
            except Exception:
                pass
            self._producer_client = None
