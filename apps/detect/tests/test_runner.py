"""End-to-end normalized evidence through isolated local JSONL outputs."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tiger_perception.config import load_workload
from tiger_perception.contracts import RawDetection, RawInference
from tiger_perception.runner import WorkloadRuntime, output_lock
from tiger_perception.sinks import validate_process_event

MANIFESTS = Path(__file__).parents[1] / "manifests"


def test_given_two_workloads_when_states_change_then_outputs_remain_independent(tmp_path):
    runtimes = []
    for cell in ("a", "b"):
        workload = load_workload(MANIFESTS / f"cell-{cell}.yaml")
        workload.spec.destination.path = str(tmp_path / cell / "events.jsonl")
        workload.spec.destination.statusPath = str(tmp_path / cell / "status.json")
        runtimes.append(WorkloadRuntime(workload))
    start = datetime.now(UTC) - timedelta(seconds=20)
    detection = RawDetection(56, "chair", 0.9, {"xMin": 0.4, "yMin": 0.4, "xMax": 0.6, "yMax": 0.6})

    for second in range(16):
        for index, runtime in enumerate(runtimes):
            present = (4 <= second < 9) if index == 0 else second >= 8
            timestamp = (start + timedelta(seconds=second)).isoformat()
            inference = RawInference(f"{index}:{second}", runtime.rule.source_id, second,
                                     timestamp, timestamp, "fixture", "fixture-model",
                                     [detection] if present else [])
            runtime.process(inference, now=datetime.fromisoformat(timestamp))

    expected = [[False, True, False], [False, True]]
    for index, runtime in enumerate(runtimes):
        events = [validate_process_event(json.loads(line))
                  for line in Path(runtime.workload.spec.destination.path).read_text().splitlines()]
        assert [event["value"] for event in events] == expected[index]
        assert all(event["sourceId"] == runtime.rule.source_id for event in events)
        assert all(event["subjectId"] == runtime.rule.subject_id for event in events)
        assert all(event["plantId"] == "demo-plant-01" for event in events)


def test_given_output_owner_when_second_instance_starts_then_reject(tmp_path):
    path = tmp_path / "events.jsonl"

    with output_lock(path), pytest.raises(ValueError, match="already owned"), output_lock(path):
        pass


def test_given_reconnect_when_first_new_frame_arrives_then_reset_pending(tmp_path):
    from tiger_perception.contracts import Frame

    workload = load_workload(MANIFESTS / "cell-a.yaml")
    runtime = WorkloadRuntime(workload)
    now = datetime.now(UTC)
    timestamp = now.isoformat()
    frame = Frame(runtime.rule.source_id, 1, timestamp, None, {"usable": True, "epoch": 0})
    runtime.accept_frame(frame)
    runtime.process(RawInference("first", runtime.rule.source_id, 1, timestamp, timestamp,
                                 "fixture", "fixture", []), now=now)

    runtime.accept_frame(replace(frame, metadata={"usable": True, "epoch": 1}))

    assert runtime.rule.availability == "unavailable"
    assert runtime.rule.confirmed is None