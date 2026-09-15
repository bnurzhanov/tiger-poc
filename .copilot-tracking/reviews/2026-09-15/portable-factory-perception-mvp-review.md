<!-- markdownlint-disable-file -->

# Review Log: Portable Factory Perception MVP

## Metadata

* Date: 2026-09-15
* Related plan: [.copilot-tracking/plans/2026-09-15/portable-factory-perception-mvp-plan.instructions.md](.copilot-tracking/plans/2026-09-15/portable-factory-perception-mvp-plan.instructions.md)
* Changes log: Missing on disk; no matching file was found under [.copilot-tracking/changes](.copilot-tracking/changes)
* Research: [.copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md](.copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md)
* Review scope: Local ProcessEvent contract, schema validation, sink behavior, detector integration, and plan adherence

## Executive Summary

The local implementation satisfies the targeted sink and detector contract and passes the focused regression tests. The review-identified Ruff blocker has been fixed and the local test, lint, and compilation checks now pass. Fabric and provider work remains explicitly deferred behind external prerequisites.

## Severity Counts

* Critical: 0
* Major: 0
* Minor: 2

## Validation Findings

### Phase 1: Lock scenario and contracts

Status: Complete for the local contract slice

Evidence:
* [.copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md](.copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md) explicitly recommends a contract-first local replay path.
* [apps/detect/tiger_perception/sinks.py](apps/detect/tiger_perception/sinks.py) validates a versioned ProcessEvent record before publication.
* The detector in [apps/detect/rtsp_yolo.py](apps/detect/rtsp_yolo.py) builds a schema-valid event payload for each processed frame.

### Phase 2: Build replay and inference adapters

Status: Partially complete

Evidence:
* The local sink and detector path are implemented and running in the repo.
* No explicit replay or provider-equivalence test files were found under [apps/detect/tests](apps/detect/tests) beyond the sink regression suite.
* The research intentionally defers full Foundry/Fabric expansion until tenant and provider readiness is proven; this is a scope gate, not an implementation defect.

### Phase 3: Map transitions and write locally

Status: Complete for the local MVP slice

Evidence:
* [apps/detect/tests/test_local_jsonl_sink.py](apps/detect/tests/test_local_jsonl_sink.py) covers valid writes, invalid payloads, outage/recovery, duplicate suppression, and detector output validation.
* The sink enforces schema validation, secret redaction, deterministic duplicate handling, and bounded outage behavior in [apps/detect/tiger_perception/sinks.py](apps/detect/tiger_perception/sinks.py).

### Phase 4-5: Fabric landing and sink expansion

Status: Deferred / external dependency

Evidence:
* The plan explicitly requires Fabric tenant enablement and preview access for phases 4 and 5.
* No Fabric landing spike or Fabric connector implementation is present in the repo at this time.
* This matches the research recommendation to defer platform-dependent work until a measured path is proven.

### Phase 6: Final validation and provider readiness

Status: Complete for the local validation slice

Evidence:
* Local pytest validation passed: `5 passed in 1.77s`.
* Ruff validation passed after fixing the six reported issues in [apps/detect/rtsp_yolo.py](apps/detect/rtsp_yolo.py), [apps/detect/tests/test_local_jsonl_sink.py](apps/detect/tests/test_local_jsonl_sink.py), [apps/detect/tiger_perception/__init__.py](apps/detect/tiger_perception/__init__.py), and [apps/detect/tiger_perception/sinks.py](apps/detect/tiger_perception/sinks.py).

## Implementation Quality Findings

### Major findings

No major findings remain for the local validation slice.

### Minor findings

1. Missing changes log artifact
   * Severity: Minor
   * Evidence: resolved by adding [.copilot-tracking/changes/2026-09-15/portable-factory-perception-mvp-changes.md](.copilot-tracking/changes/2026-09-15/portable-factory-perception-mvp-changes.md).
   * Impact: Review traceability is now present.
   * Recommendation: Keep the changes log synchronized with future implementation phases.

2. Fabric and provider phases remain unproven in the repository
   * Severity: Minor
   * Evidence: plans and research explicitly defer those phases pending external tenant access, while the repository currently contains only the local sink path.
   * Impact: The broader architecture is documented but not yet demonstrated in this workspace.
   * Recommendation: Keep the local contract as the verified MVP boundary and record the external blockers before expanding scope.

## Validation Command Output

### Command 1

```text
cd /home/dakir/tiger-poc && uv run --project apps/detect pytest apps/detect/tests -q -s
```

Result:

```text
....process_event: {'eventId': 'camera-01-frame-42', 'eventType': 'ProcessEvent', 'sourceId': 'camera-01', 'value': 2, 'confidence': 1.0, 'detection_count': 2}
.
5 passed in 1.77s
```

Status: Pass

### Command 2

```text
cd /home/dakir/tiger-poc && uv run --project apps/detect ruff check apps/detect
```

Result after rework:

```text
All checks passed.
```
Status: Pass
Status: Fail

### Command 3

```text
cd /home/dakir/tiger-poc && uv run --project apps/detect python -m compileall -q apps/detect
```

Status: Pass, exit code 0.

## Missing Work and Deviations

* The repository does not yet contain the Fabric landing spike or selected Fabric sink implementation required by phases 4 and 5.
* The local path is functionally, stylistically, and syntactically validated.

## Follow-Up Work

### Deferred from scope

* Complete the Fabric landing and Digital twin builder spike once tenant access is available.
* Prove provider equivalence and readiness for Foundry cloud or Foundry Local only after the environment is available.

### Discovered during review

* Complete the Fabric landing and provider-readiness work when the required external access is available.

## Overall Status

Status: Complete for the local validation slice

The local ProcessEvent implementation is functionally correct and verified by passing pytest, Ruff, and compileall checks. The broader Fabric and Foundry phases remain deferred rather than failed.
