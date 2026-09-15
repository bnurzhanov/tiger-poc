<!-- markdownlint-disable-file -->
# Implementation Details: Portable Factory Perception MVP

## Context Reference

Sources: .copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md; docs/mvp-design.md; apps/detect/rtsp_yolo.py; manifest.yaml; apps/detect/pyproject.toml

## Implementation Phase 1: Lock the scenario and contracts

<!-- parallelizable: false -->

### Step 1.1: Select the first scenario and event

Resolve the conflict between the line-monitoring/Fabric proposal and the aisle-inventory/WMS manifest before implementation. Select one measurable value for the first demo, preferably a deterministic count or occupancy state, and document subject identity, units, confidence semantics, event-time policy, and transition semantics.

Files:
* manifest.yaml - Reconcile the workload name, provider, ontology, and destination with the selected scenario, or explicitly mark it as deferred configuration.
* docs/mvp-design.md - Update the MVP contract and demo assumptions with the selected first event and Fabric landing assumption.
* .copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md - Preserve the evidence and decision record if the selected path differs from the recommendation.

Discrepancy references:
* DD-01 and DD-02 in the planning log.

Success criteria:
* One scenario, one first event, and one intended Fabric destination are named consistently.
* No secret, endpoint, or credential is added to configuration or documentation.

Context references:
* manifest.yaml (Lines 1-22) - Current aisle inventory/WMS declaration.
* docs/mvp-design.md (Lines 97-151) - Intended component contracts and Fabric boundary.
* .copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md (Lines 300-340) - Open decisions and recommended first slice.

Dependencies:
* Owner decision on scenario, or adoption of the recommended line-monitoring/Fabric default.

### Step 1.2: Add versioned typed contracts and schemas

Create standard-library data models and protocols for Frame, RawDetection, RawInference, Observation, ProcessEvent, and Sink. Separate capturedAt, producedAt, and publishedAt. Give events stable IDs, schemaVersion, source/provider/model metadata, typed values, and an explicit unresolved-subject representation. Preserve raw detections as diagnostic evidence.

Files:
* apps/detect/tiger_perception/contracts.py - Typed models and Sink protocol.
* apps/detect/tiger_perception/schemas/process-event-v1.json - Versioned event schema.
* apps/detect/tests/fixtures/process-event-valid.json - Positive contract fixture.
* apps/detect/tests/fixtures/process-event-invalid.json - Negative contract fixture.
* apps/detect/tests/test_contracts.py - Serialization, schema, timestamp, and secret-redaction assertions.

Discrepancy references:
* DR-01 and DR-02 in the planning log.

Success criteria:
* The schema rejects missing IDs, invalid timestamps, unsupported value types, and malformed confidence values.
* Event identity and deduplication inputs are deterministic for the same source, sequence, and transition.

Context references:
* .copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md (Lines 75-130) - Capture, observation, and mapper contract requirements.
* apps/detect/rtsp_yolo.py (Lines 97-122) - Existing raw detection fields.

Dependencies:
* Step 1.1 scenario decision.

## Implementation Phase 2: Build replay and inference adapters

<!-- parallelizable: false -->

### Step 2.1: Extract capture and inference boundaries

Introduce a prerecorded replay adapter and retain an RTSP adapter that emit the same Frame contract. Add deterministic fake inference for tests and demos, then adapt the existing YOLO extraction path to RawInference. Define a bounded queue, maximum in-flight work, and backpressure/drop policy at the capture-to-inference boundary. Keep rtsp_yolo.py as a compatibility CLI wrapper while moving reusable work into modules.

Files:
* apps/detect/tiger_perception/capture.py - Replay and RTSP frame sources.
* apps/detect/tiger_perception/inference.py - Fake and YOLO inference providers.
* apps/detect/rtsp_yolo.py - Compatibility wrapper delegating to the pipeline.
* apps/detect/tests/test_replay.py - Deterministic replay and end-of-input tests.
* apps/detect/tests/test_inference.py - Provider contract tests.
* apps/detect/tests/test_pipeline_flow.py - Queue bounds, backpressure, and dropped-frame accounting tests.

Discrepancy references:
* DR-03 in the planning log.

Success criteria:
* The checked-in fixture or a short local clip can run without a camera or network credential.
* The current RTSP CLI remains runnable and produces contract-compatible raw inference output.
* Replay produces identical frame sequence and event-time inputs across repeated runs.
* Queue growth is bounded and the selected drop/backpressure policy is observable in metrics.

Context references:
* apps/detect/rtsp_yolo.py (Lines 125-180) - Current monolithic capture/inference loop.
* .copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md (Lines 170-205) - Required replay and provider boundary.

Dependencies:
* Phase 1 contracts.

### Step 2.2: Validate the adapter slice

Run focused tests and static checks before adding mapping or sinks.

Validation commands:
* `uv run --project apps/detect pytest apps/detect/tests/test_contracts.py apps/detect/tests/test_replay.py apps/detect/tests/test_inference.py`
* `uv run --project apps/detect ruff check apps/detect`

### Step 2.3: Compare providers on identical replay input

Run the same deterministic replay through two available inference providers, at minimum the fake provider and the current YOLO adapter. Compare ProcessEvent shape, stable identifiers, timestamps, and permitted semantic differences; record provider/model metadata and any mismatch. This is a contract and event-level comparison, not an assumption that raw detections are identical.

Files:
* apps/detect/tests/test_provider_equivalence.py - Same-input provider comparison and permitted-difference assertions.
* docs/inference-provider-readiness.md - Measured comparison results and unresolved provider gaps.

Discrepancy references:
* DR-06 in the planning log.

Success criteria:
* Both providers produce contract-valid events for the same replay input.
* Differences are limited to documented provider/model metadata or explicitly recorded semantic variation.

Dependencies:
* Step 2.1 provider adapters and Phase 1 event schema.

## Implementation Phase 3: Map transitions and write locally

<!-- parallelizable: false -->

### Step 3.1: Implement the stateful mapper

Implement one scenario-specific mapper that accepts normalized observations, tracks the minimum prior state, debounces repeated identical observations, and emits only the defined transition events. Use deterministic event IDs and explicit behavior for low confidence, unresolved subjects, restart, and out-of-order observations.

Files:
* apps/detect/tiger_perception/mapper.py - Stateful mapper and rule configuration.
* apps/detect/tests/test_mapper.py - Repetition, transition, restart, ordering, and confidence tests.

Discrepancy references:
* DR-04 in the planning log.

Success criteria:
* Replaying unchanged observations does not create duplicate state-change events.
* A single state transition creates exactly one stable event.
* Restart and retry behavior is documented and covered by tests.

Context references:
* .copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md (Lines 131-169) - Event semantics and duplicate-state risks.

Dependencies:
* Phase 2 normalized inference output.

### Step 3.2: Add local schema-validating sink

Implement a local JSONL sink with flush behavior, bounded retry hooks, redaction, and captured payload replay. Validate every ProcessEvent before writing and expose counters for sink attempts, successes, failures, and last successful publication.

Files:
* apps/detect/tiger_perception/sinks.py - Sink protocol implementation and validation.
* apps/detect/tests/test_sinks.py - Positive, negative, retry, redaction, outage, recovery, and duplicate tests.
* apps/detect/detections.jsonl - Retain as transport evidence; do not treat it as factory-semantic validation.
* apps/detect/README.md - Document the deterministic replay command and local fallback output.

Discrepancy references:
* DR-05 in the planning log.

Success criteria:
* Local replay produces a versioned, schema-valid ProcessEvent JSONL file.
* Invalid events fail before publication and secrets are absent from logs and payloads.
* Sink failure tests demonstrate bounded retry and deterministic duplicate behavior.
* Stopping the sink, generating events, and restoring it demonstrates documented recovery without silent loss.

Context references:
* .copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md (Lines 206-239) - Reliability, security, and fallback requirements.

Dependencies:
* Step 3.1 mapper output.

### Step 3.3: Validate the local MVP slice

Validation commands:
* `uv run --project apps/detect pytest apps/detect/tests`
* `uv run --project apps/detect ruff check apps/detect`
* `uv run --project apps/detect python -m compileall -q apps/detect`

## Implementation Phase 4: Run the Fabric landing and mapping spike

<!-- parallelizable: true -->

### Step 4.1: Prove the Eventstream-to-table path

Using the versioned ProcessEvent draft, select the Eventstream custom-app protocol and destination, publish ten records with a named executable publisher or documented portal procedure, inspect landing schema and timestamps, and record authentication, network, delay, and failure behavior. Do not implement a production connector until this experiment identifies the actual protocol and landing destination.

Files:
* docs/fabric-landing-spike.md - Tenant prerequisites, selected protocol, destination, observed schema, timing, and blockers.
* tools/fabric_landing_spike.py or an equivalent documented Eventstream portal procedure - Reproducible ten-record publisher with redacted configuration inputs.
* apps/detect/tests/fixtures/fabric-captured-events.jsonl - Redacted captured payloads for replay, if permitted.

Discrepancy references:
* DR-06 in the planning log.

Success criteria:
* The landing destination required by Digital twin builder mapping is confirmed or explicitly blocked.
* The experiment records end-to-end delay and does not expose credentials.

Context references:
* .copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md (Lines 240-300) - Eventstream and Digital twin builder constraints.

Dependencies:
* Phase 1 event schema draft; Fabric tenant, capacity, and preview access.

Execution note:
* Phase 4 may run alongside Phases 1-3, but Step 4.2 is sequential after Step 4.1 and both steps have one owner for docs/fabric-landing-spike.md.

### Step 4.2: Prove one Digital twin builder mapping

Manually configure one stable entity ID and one property or time-series value, run mapping on demand and on schedule, and record whether the visible update meets the intended demo target. Capture immutable naming and type decisions.

Files:
* docs/fabric-landing-spike.md - Mapping configuration and observed refresh behavior.

Success criteria:
* One complete landing-to-mapping path is demonstrated, or the exact tenant/platform blocker is recorded.
* The five-minute target is reported as an observed result, not an assumption.

Dependencies:
* Step 4.1 landing destination.

## Implementation Phase 5: Add the selected Fabric sink

<!-- parallelizable: false -->

### Step 5.1: Implement the transport behind Sink

Implement only the protocol selected by the landing spike. Keep ProcessEvent and mapper code Fabric-independent. Add TLS verification, secret references, bounded exponential retry with jitter, idempotency keys, redacted structured logging, and metrics. Retain LocalJsonlSink as the offline fallback.

Files:
* apps/detect/tiger_perception/sinks.py - Selected Fabric sink and shared retry/metrics behavior.
* apps/detect/tests/test_fabric_sink.py - Contract, retry, idempotency, and redaction tests using captured transport responses.
* apps/detect/README.md - Fabric configuration references and offline fallback instructions.

Discrepancy references:
* DD-03 in the planning log.

Success criteria:
* Changing inference provider does not change connector code or event schema.
* Transient sink failures retry within bounds; permanent failures are visible and do not silently discard events.
* No credentials appear in the manifest, logs, event payloads, or exception text.

Dependencies:
* Phase 4 selected protocol and destination.

## Implementation Phase 6: Final validation and deferred provider readiness

<!-- parallelizable: false -->

### Step 6.1: Validate the complete local and integration paths

Run the full project checks and rehearse the replay-first demo. Run one live-camera smoke test only when RTSP access is available, including disconnect/reconnect behavior. Record metrics for frames read, processed, dropped, inference latency, mapper events, sink outcomes, and last publication. Fix isolated validation failures and rerun the affected check; for blockers beyond minor corrections, record the owner, evidence, impact, and recommended next planning action.

Validation commands:
* `uv run --project apps/detect pytest apps/detect/tests`
* `uv run --project apps/detect ruff check apps/detect`
* `uv run --project apps/detect python -m compileall -q apps/detect`

Success criteria:
* Local replay reaches a visible local sink in under five minutes.
* Contract, mapper, sink, and failure tests pass.
* RTSP compatibility is preserved or the blocker is documented.
* Validation fixes are rerun successfully, or every unresolved blocker has an owner and evidence record.

### Step 6.2: Gate Foundry provider expansion

Create a readiness checklist for Foundry cloud and Foundry Local on Azure Local covering access, cluster versions, gateway/TLS, model format and image input, identity, hardware, latency, throughput, and data egress. Do not make this work a dependency of the local MVP.

Files:
* docs/inference-provider-readiness.md - Provider prerequisites, measured results, and go/no-go decision.

Discrepancy references:
* DR-07 in the planning log.

Success criteria:
* Provider expansion is either proven with measured event-level equivalence or explicitly deferred with named blockers.

Dependencies:
* Complete local contract and mapper path; platform access for any live test.

## Dependencies

* Python 3.14 and uv
* Existing OpenCV and Ultralytics dependencies
* pytest and Ruff
* Fabric tenant, capacity, Digital twin builder preview enablement, and Eventstream access for Phase 4
* Foundry provider access and Azure Local/Arc/Kubernetes prerequisites only for Phase 6.2

## Success Criteria

* A deterministic replay pipeline emits schema-valid, debounced ProcessEvent records through a local sink.
* RTSP remains a compatible capture path.
* The Fabric landing-to-mapping path is proven or its blocker is recorded with evidence.
* Provider changes remain behind the inference boundary and do not require connector changes.
* The repository has repeatable commands, focused tests, and a documented offline demo path.
