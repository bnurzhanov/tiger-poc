"""Map a resolved boolean observation to the existing versioned event schema."""

from datetime import UTC, datetime

from .config import Workload
from .contracts import Observation, ProcessEvent
from .sinks import validate_process_event


def map_presence(observation: Observation, workload: Workload) -> dict[str, object]:
    """Preserve observation identity on retries and attach deployment metadata."""
    source = workload.spec.source
    if (observation.subject_resolution != "resolved"
            or observation.subject_id != source.subjectId
            or observation.source_id != source.id
            or type(observation.value) is not bool
            or observation.observation_type != workload.spec.perception.observationType):
        raise ValueError("Only a resolved boolean observation for this workload can be mapped")
    event = ProcessEvent(
        event_id=observation.observation_id, source_id=source.id,
        subject_id=source.subjectId, observation_type=observation.observation_type,
        value=observation.value, unit="boolean", confidence=observation.confidence,
        captured_at=observation.captured_at, produced_at=observation.produced_at,
        published_at=datetime.now(UTC).isoformat(), provider=observation.provider,
        model=observation.model, source=source.type, observation=observation.metadata,
    ).to_dict()
    event.update(plantId=workload.metadata.plantId, plantName=workload.metadata.plantName)
    return validate_process_event(event)