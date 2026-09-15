<!-- markdownlint-disable-file -->
# Release Changes: Portable Factory Perception MVP

**Related Plan**: portable-factory-perception-mvp-plan.instructions.md
**Implementation Date**: 2026-09-15

## Summary

Completed and validated the local ProcessEvent publication slice. The detector publishes schema-valid events through the local JSONL sink, tests expose observable output, and the touched Python files now pass Ruff and compilation checks.

## Changes

### Added

* `.copilot-tracking/reviews/2026-09-15/portable-factory-perception-mvp-review.md` - Review record for the local implementation and validation findings.
* `.copilot-tracking/changes/2026-09-15/portable-factory-perception-mvp-changes.md` - Implementation change tracking and validation record.

### Modified

* `apps/detect/rtsp_yolo.py` - Sorted imports and removed the unused `json` import.
* `apps/detect/tests/test_local_jsonl_sink.py` - Sorted imports.
* `apps/detect/tiger_perception/__init__.py` - Formatted the multiline export import.
* `apps/detect/tiger_perception/sinks.py` - Removed the unused `Sequence` import and used explicit exception string conversion.

### Removed

None.

## Additional or Deviating Changes

* Fabric landing, Digital twin builder mapping, Fabric sink implementation, and Foundry provider equivalence remain deferred.
  * These phases require external tenant, preview, provider, or hardware access and were explicitly identified as external dependencies in the plan and research.
* The existing local tests remain concentrated in `test_local_jsonl_sink.py`.
  * No unrelated test restructuring was introduced during validation rework.

## Validation

* `uv run --project apps/detect pytest apps/detect/tests -q -s` - Passed, 5 tests.
* `uv run --project apps/detect ruff check apps/detect` - Passed.
* `uv run --project apps/detect python -m compileall -q apps/detect` - Passed.
  * Existing third-party SyntaxWarnings were emitted from the virtual environment; no application compilation errors occurred.

## Release Summary

The local perception publication path is cleanly validated. Four application files were modified for lint correctness, one review artifact and this changes log were added, and no deployment or dependency changes were made. The broader Fabric and Foundry integration work remains a separately gated follow-on effort.
