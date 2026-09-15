"""Tiger Factory Perception and Fabric Ingestion package."""

from .contracts import (
    Frame,
    Observation,
    ProcessEvent,
    RawDetection,
    RawInference,
    Sink,
)
from .presence import PresenceRuleConfig, RegionConfig, RegionPresenceRule
from .sinks import (
    FabricEventstreamSink,
    LocalJsonlSink,
    SinkError,
    SinkUnavailableError,
    validate_process_event,
)

__all__ = [
    "FabricEventstreamSink",
    "Frame",
    "LocalJsonlSink",
    "Observation",
    "PresenceRuleConfig",
    "ProcessEvent",
    "RawDetection",
    "RawInference",
    "RegionConfig",
    "RegionPresenceRule",
    "Sink",
    "SinkError",
    "SinkUnavailableError",
    "validate_process_event",
]
