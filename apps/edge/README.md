# Factory Edge Perception & Microsoft Fabric Ingestion

This component runs the localized edge perception workload and dispatches confirmed `ProcessEvent` records to Microsoft Fabric Eventstream (or local JSON Lines sinks for offline validation).

## Features

- **Manifest-Driven Deployment**: Configure camera sources, ROI boundaries, confidence thresholds, and plant metadata without changing code.
- **Stateful Presence Engine**: Applies temporal confirmation windows to eliminate jitter and suppresses duplicate events.
- **Hybrid Fabric Ingestion**:
  - Direct ingestion into Fabric Eventstream via Azure Event Hubs protocol or REST endpoints.
  - Automatic offline `--dry-run` mode with local `.jsonl` tracing when cloud connectivity is disabled.
- **Multi-Cell Simulation**: Built-in deterministic replay generator for validating independent cell transitions (`Cell A` and `Cell B`).

## Quickstart

### 1. Run Tests

```bash
uv run --project apps/edge pytest apps/edge/tests
```

### 2. Run Multi-Cell Simulation (Replay Generator)

Simulate 2 manufacturing cells producing pallet occupancy transitions:

```bash
# Dry-run mode (local output & console log)
uv run --project apps/edge python apps/edge/tiger_perception/replay.py --sink both --output simulation.jsonl

# Live streaming to Microsoft Fabric Eventstream
export FABRIC_EVENTSTREAM_CONNECTION_STRING="<EventHubConnectionStringFromInfra>"
uv run --project apps/edge python apps/edge/tiger_perception/replay.py --sink fabric --live-fabric
```

### 3. Run Pipeline with Workload Manifest

```bash
uv run --project apps/edge python apps/edge/tiger_perception/pipeline.py \
  --manifest apps/edge/manifests/cell-a-workload.yaml \
  --output detections-cell-a.jsonl
```
