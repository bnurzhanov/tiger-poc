<!-- markdownlint-disable-file -->
---
applyTo: '.copilot-tracking/changes/2026-09-15/portable-factory-perception-mvp-changes.md'
---
# Implementation Plan: Portable Factory Perception MVP

## Overview

Build a contract-first, deterministic replay pipeline that normalizes frame inference into debounced process events, validates them locally, and proves the actual Fabric landing-to-Digital twin builder path before adding a production Fabric sink.

## Objectives

### User Requirements

* Create an actionable implementation plan from the supplied portable-factory perception research — Source: user-provided task-plan prompt and attached research.
* Preserve a reusable pipeline boundary across replay, RTSP, inference providers, mapping, and sinks — Source: docs/mvp-design.md and attached research.
* Support a local fallback while Fabric and Foundry platform prerequisites are validated — Source: attached research, Recommended first slice.

### Derived Objectives

* Resolve the line-monitoring/Fabric versus aisle-inventory/WMS contradiction before implementation — Derived from manifest.yaml being unused and inconsistent with the proposal.
* Version and test Frame, RawInference, Observation, ProcessEvent, and Sink contracts — Derived from the research finding that the current JSONL record is not an observation or process event.
* Prevent duplicate state events with deterministic identity, state memory, and debounce — Derived from the research's event semantics and reliability risks.
* Make the Fabric connector depend on a measured landing protocol and destination — Derived from the documented Digital twin builder lakehouse/table mapping path.
* Defer Foundry Local on Azure Local until access, model, endpoint, and hardware requirements are proven — Derived from the research's unverified-provider constraints.

## Context Summary

### Project Files

* manifest.yaml - Unread PerceptionWorkload configuration that conflicts with the Fabric line-monitoring proposal.
* docs/mvp-design.md - Intended capture, perception, mapper, Fabric connector, runtime mode, demo, and validation boundaries.
* apps/detect/rtsp_yolo.py - Monolithic RTSP, YOLO inference, JSONL serialization, and CLI implementation.
* apps/detect/detections.jsonl - Generic object-detection transport fixture, not factory-semantic validation.
* apps/detect/pyproject.toml - Python 3.14 project with OpenCV, Ultralytics, pytest, and Ruff.
* apps/detect/README.md - Current setup and RTSP execution documentation.

### References

* .copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md - Primary architecture review, platform constraints, risks, alternatives, experiments, and recommended sequence.
* docs/mvp-design.md - Local product design and original implementation sequence.

### Standards References

* /home/dakir/.vscode-server/extensions/ise-hve-essentials.hve-core-all-3.3.101/.github/instructions/hve-core/markdown.instructions.md - Required frontmatter, Markdown structure, and tracking-file conventions.
* /home/dakir/.vscode-server/extensions/ise-hve-essentials.hve-core-all-3.3.101/.github/instructions/hve-core/writing-style.instructions.md - Required concise technical writing style.

## Implementation Checklist

### [ ] Implementation Phase 1: Lock scenario and contracts

<!-- parallelizable: false -->

* [ ] Step 1.1: Select the first line-monitoring event and reconcile manifest.yaml with the selected scope.
  * Details: .copilot-tracking/details/2026-09-15/portable-factory-perception-mvp-details.md (Lines 9-31)
* [x] Step 1.2: Add versioned typed contracts, JSON Schema, fixtures, and contract tests.
  * Details: .copilot-tracking/details/2026-09-15/portable-factory-perception-mvp-details.md (Lines 32-63)

### [ ] Implementation Phase 2: Build replay and inference adapters

<!-- parallelizable: false -->

* [ ] Step 2.1: Extract replay, RTSP, fake, and YOLO provider boundaries while preserving the current CLI.
  * Details: .copilot-tracking/details/2026-09-15/portable-factory-perception-mvp-details.md (Lines 65-92)
* [ ] Step 2.2: Run focused adapter tests, Ruff, and compilation.
  * Details: .copilot-tracking/details/2026-09-15/portable-factory-perception-mvp-details.md (Lines 93-100)
* [ ] Step 2.3: Compare two inference providers on identical replay input and record event-level equivalence.
  * Details: .copilot-tracking/details/2026-09-15/portable-factory-perception-mvp-details.md (Lines 101-122)

### [ ] Implementation Phase 3: Map transitions and write locally

<!-- parallelizable: false -->

* [ ] Step 3.1: Implement one stateful, debounced mapper with deterministic event identity.
  * Details: .copilot-tracking/details/2026-09-15/portable-factory-perception-mvp-details.md (Lines 123-144)
* [x] Step 3.2: Implement a schema-validating local JSONL sink with redaction, retries, and metrics.
  * Details: .copilot-tracking/details/2026-09-15/portable-factory-perception-mvp-details.md (Lines 145-168)
* [x] Step 3.3: Run the complete local test, lint, and compile checks.
  * Details: .copilot-tracking/details/2026-09-15/portable-factory-perception-mvp-details.md (Lines 169-179)

### [ ] Implementation Phase 4: Run Fabric landing and mapping spike

<!-- parallelizable: true -->

* [ ] Step 4.1: Publish a small batch through the selected Eventstream custom-app protocol and confirm the landing table/schema.
  * Details: .copilot-tracking/details/2026-09-15/portable-factory-perception-mvp-details.md (Lines 180-204)
* [ ] Step 4.2: Manually map one stable entity and property or time-series value in Digital twin builder and measure refresh behavior.
  * Details: .copilot-tracking/details/2026-09-15/portable-factory-perception-mvp-details.md (Lines 205-222)

### [ ] Implementation Phase 5: Add the selected Fabric sink

<!-- parallelizable: false -->

* [ ] Step 5.1: Implement the measured transport behind Sink with retry, idempotency, TLS, redaction, and metrics.
  * Details: .copilot-tracking/details/2026-09-15/portable-factory-perception-mvp-details.md (Lines 223-246)

### [ ] Implementation Phase 6: Final validation and provider readiness

<!-- parallelizable: false -->

* [ ] Step 6.1: Run full validation and rehearse replay and live-camera smoke paths.
  * Details: .copilot-tracking/details/2026-09-15/portable-factory-perception-mvp-details.md (Lines 247-260)
* [ ] Step 6.2: Gate Foundry cloud and Foundry Local expansion behind a measured readiness checklist.
  * Details: .copilot-tracking/details/2026-09-15/portable-factory-perception-mvp-details.md (Lines 261-279)

## Planning Log

See .copilot-tracking/plans/logs/2026-09-15/portable-factory-perception-mvp-log.md for discrepancy tracking, implementation paths, and suggested follow-on work.

## Dependencies

* Python 3.14 and uv
* OpenCV and Ultralytics dependencies already declared in apps/detect/pyproject.toml
* pytest and Ruff
* Fabric tenant, capacity, Digital twin builder preview enablement, and Eventstream access for Phase 4
* Foundry and Azure Local/Arc/Kubernetes access only for provider expansion

## Success Criteria

* Deterministic replay emits schema-valid, debounced ProcessEvent records to a local sink — Traces to: attached research, Recommended first slice.
* RTSP remains a compatible capture path and the existing CLI remains usable — Traces to: apps/detect/rtsp_yolo.py and research, Proposed implementation sequence.
* Fabric landing and Digital twin builder mapping are demonstrated or blocked with recorded evidence — Traces to: attached research, Fabric constraints and revised success criteria.
* Provider changes do not require mapper or connector changes — Traces to: docs/mvp-design.md, Runtime Modes.
* The repository contains repeatable focused tests and an offline demo path — Traces to: attached research, Revised success criteria.
