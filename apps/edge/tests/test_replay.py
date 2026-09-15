"""Tests for multi-cell replay generator."""

from __future__ import annotations

from pathlib import Path

from tiger_perception.replay import generate_scenario_events, run_simulation


def test_given_scenario_generator_when_called_then_produces_independent_cell_events() -> None:
    events = generate_scenario_events()
    assert len(events) == 6

    cell_a_events = [e for e in events if "cell-a" in e["subjectId"]]
    cell_b_events = [e for e in events if "cell-b" in e["subjectId"]]

    assert len(cell_a_events) == 3
    assert len(cell_b_events) == 3

    # Check cell A sequence: Empty -> Occupied -> Empty
    assert cell_a_events[0]["value"] is False
    assert cell_a_events[1]["value"] is True
    assert cell_a_events[2]["value"] is False


def test_given_simulation_run_when_executed_then_writes_jsonl_output(tmp_path: Path) -> None:
    output_file = tmp_path / "test-sim.jsonl"
    total = run_simulation(
        sink_type="local",
        output_path=output_file,
        interval_seconds=0.0,
        iterations=1,
    )
    assert total == 6
    assert output_file.exists()
