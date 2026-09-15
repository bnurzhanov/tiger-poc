"""Manifest and mapping checks without cameras or inference dependencies."""

from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from tiger_perception.config import load_workload, resolve_source
from tiger_perception.contracts import Observation
from tiger_perception.mapping import map_presence

MANIFESTS = Path(__file__).parents[1] / "manifests"


@pytest.mark.parametrize("cell", ["a", "b"])
def test_given_manifest_when_loaded_then_paths_and_identity_are_independent(cell):
    workload = load_workload(MANIFESTS / f"cell-{cell}.yaml")

    assert workload.spec.source.id == f"cell-{cell}-camera-01"
    assert Path(workload.spec.destination.path).parts[-2:] == (f"cell-{cell}", "events.jsonl")
    assert Path(workload.spec.perception.model).is_file()


@pytest.mark.parametrize("section,field,value", [
    ("region", "bounds", [0.8, 0.2, 0.1, 0.9]),
    ("region", "coordinates", "pixels"), ("source", "subjectId", ""),
    ("presence", "staleSeconds", 0), ("presence", "confidence", float("nan")),
    ("presence", "emptySeconds", -1), ("presence", "confidence", True),
    ("perception", "observationType", "PalletPresent"),
    ("perception", "sampleEveryFrames", 0), ("perception", "provider", "foundry-local"),
])
def test_given_invalid_settings_when_loading_then_fail_without_value_leak(tmp_path, section, field, value):
    document = yaml.safe_load((MANIFESTS / "cell-a.yaml").read_text())
    document["spec"][section][field] = value
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(document))

    with pytest.raises(ValueError):
        load_workload(path)


def test_given_missing_reference_when_resolving_then_clear_error(monkeypatch):
    workload = load_workload(MANIFESTS / "cell-a.yaml")
    monkeypatch.delenv("CAMERA_A_RTSP_URL", raising=False)

    with pytest.raises(ValueError, match="CAMERA_A_RTSP_URL"):
        resolve_source(workload.spec.source)


def test_given_pallet_templates_when_loaded_then_shared_model_and_distinct_positions():
    first = load_workload(MANIFESTS.parents[2] / "manifest.yaml")
    second = load_workload(MANIFESTS / "cell-b-pallet.yaml")

    assert first.spec.perception.model == second.spec.perception.model
    assert first.spec.perception.observationType == second.spec.perception.observationType == "PalletPresent"
    assert first.spec.source.subjectId != second.spec.source.subjectId
    assert first.spec.destination.path != second.spec.destination.path


@pytest.mark.parametrize("cell,present", [("a", True), ("b", False)])
def test_given_confirmed_observation_when_mapping_then_preserve_identity_metadata_and_retry_id(cell, present):
    workload = load_workload(MANIFESTS / f"cell-{cell}.yaml")
    timestamp = "2026-09-15T12:00:00+00:00"
    observation = Observation("stable-retry-id", workload.spec.source.id, "ObjectPresent",
                              present, 0.8 if present else 0.0, timestamp, timestamp,
                              "ultralytics", "yolo26n.pt", workload.spec.source.subjectId,
                              "resolved", "boolean")

    event = map_presence(observation, workload)

    assert event["eventId"] == map_presence(observation, workload)["eventId"]
    assert event["value"] is present
    assert event["plantId"] == "demo-plant-01"
    assert event["plantName"] == "Demo Plant"
    assert event["subjectId"] == workload.spec.source.subjectId
    with pytest.raises(ValueError):
        map_presence(replace(observation, subject_resolution="unresolved"), workload)