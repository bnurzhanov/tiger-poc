<!-- markdownlint-disable-file -->
---
title: Portable Factory Perception MVP Research
description: Skeptical architecture review of the portable factory perception proposal and repository evidence
ms.date: 2026-09-15
ms.topic: research
---

## Executive conclusion

Status: Complete.

The proposal is a useful hypothesis, but the repository is still a detector prototype rather than an implementation of the proposed portable pipeline. The only demonstrated path is Python/OpenCV RTSP capture, Ultralytics YOLO inference, and JSON Lines file output. There is no observation contract, event mapper, inference-provider adapter, Fabric connector, prerecorded-video path, test suite, deployment artifact, or executable interpretation of the root manifest.

The highest-risk assumption is the statement that an Eventstream can be the only Fabric-specific integration point while Digital twin builder updates an ontology from the emitted process events. Current Microsoft documentation describes Eventstream custom app ingestion, then Digital twin builder mapping from Fabric lakehouse source tables and scheduled or on-demand mapping/contextualization flows. That is compatible with the proposal only if the design adds and proves a Fabric-side landing/table/mapping path. A direct event-to-ontology update should be treated as unverified, not as the default connector behavior.

Recommended first slice: implement a deterministic replay pipeline with explicit `Frame`, `Observation`, `ProcessEvent`, and `Sink` contracts; run it against the existing JSONL fixture; provide a local sink and a schema-validated Eventstream payload sink; then validate the actual Fabric landing-to-mapping path with one manually configured Digital twin builder item. Defer Foundry Local on Azure Local until access, cluster, model, endpoint, and GPU/CPU requirements are proven.

## Evidence classification

* **Evidenced:** directly visible in repository code, repository data, or the cited Microsoft documentation.
* **Plausible:** technically reasonable, but not demonstrated by this repository or guaranteed by the cited platform behavior.
* **Unverified:** a proposal claim that requires a tenant, hardware, access, or end-to-end experiment before it can be relied upon.

## Repository evidence

### Structure and maturity

**Evidenced:** the repository contains one root manifest, two design documents, and one detector application. The detector application contains `rtsp_yolo.py`, `README.md`, `pyproject.toml`, `uv.lock`, `.python-version`, a YOLO weights file, and a generated `detections.jsonl` fixture. There are no source modules for capture, observation, mapping, Fabric, or cloud inference, and no visible test, CI, Docker, Kubernetes, Bicep, Terraform, or Fabric item configuration files.

The implementation maturity is therefore **runnable proof of local detection**, not MVP pipeline maturity. The documentation is ahead of the code: `docs/mvp-design.md` describes composable blocks and two runtime modes, while the repository currently exposes one monolithic executable.

### Actual detector interface

The concrete command-line and runtime interface is:

* `apps/detect/rtsp_yolo.py:1-7` documents an RTSP URL and `uv run` invocation.
* `apps/detect/rtsp_yolo.py:21-29` defines a default model, default JSONL output, and a default RTSP URL.
* `apps/detect/rtsp_yolo.py:34-83` defines CLI options: RTSP URL, model path/name, output path, camera ID, confidence, frame stride, maximum processed frames, and verbose logging.
* `apps/detect/rtsp_yolo.py:87-94` validates only confidence, frame stride, and maximum frames. It does not validate model capability, labels, output schema, timestamp policy, or endpoint credentials.
* `apps/detect/rtsp_yolo.py:97-122` converts Ultralytics `Results` into dictionaries containing `classId`, `label`, `confidence`, and pixel-coordinate `boundingBox` values.
* `apps/detect/rtsp_yolo.py:125-180` owns model construction, `cv2.VideoCapture`, frame skipping, inference, timestamp creation, JSON serialization, file flushing, and loop termination.
* `apps/detect/rtsp_yolo.py:183-201` maps failures to process exit codes. There is no retry policy, reconnect policy, health signal, graceful output finalization, or metrics export.

The current output is a **frame detection record**, not the proposal's observation. It has `cameraId`, wall-clock `timestamp`, `frameNumber`, and a list of detections. It does not have `subjectId`, `observationType`, scalar `value`, a source/provider identity, model version, event time versus processing time, or a stable event ID.

`apps/detect/detections.jsonl:1-2` also demonstrates a semantic mismatch: the checked-in sample contains `potted plant` and `dining table` detections from a generic model, not factory entities such as pallets, products, stations, or process states. This is useful as a transport fixture, but it cannot validate the line-monitoring ontology or the proposed business rule.

### Actual configuration interface

`manifest.yaml:1-22` declares a `PerceptionWorkload` called `aisle-cycle-count`, with an RTSP source, `foundry-local` provider, `pallet-counter` model, `PalletCount` observation type, a frame sampling value, an inventory discrepancy rule, and a WMS destination. Nothing in the repository reads this YAML. It also contradicts the proposal's stated destination: it names `inventory-system`, `WMS_ENDPOINT`, and `WMS_CREDENTIAL`, while the proposal says the MVP connector targets Fabric Eventstream and Digital twin builder.

`apps/detect/README.md:7-17` documents `uv sync` and a direct detector command. It does not document `manifest.yaml`, prerecorded input, Foundry, Fabric, credentials, or a repeatable ontology update. `apps/detect/pyproject.toml:1-10` provides Python packaging and dependencies, including OpenCV, Ultralytics, pytest, and Ruff, but the presence of pytest is not evidence of tests; no test files were found.

## Boundary and contract analysis

### Capture boundary

The proposal says capture emits timestamped frames, but the implementation currently performs capture inside `run()` and passes raw OpenCV frames directly into `model.predict()` (`apps/detect/rtsp_yolo.py:125-164`). There is no frame type or capture interface.

Required contract decisions:

* Distinguish source/capture time from processing/publication time.
* Define frame identity as `(sourceId, sequence)` or an equivalent stable key.
* Define behavior for decode failure, end of prerecorded input, RTSP reconnect, and clock skew.
* State whether frames are copied, encoded, or passed as in-memory arrays.
* Bound memory and queue behavior if inference is slower than capture.

The smallest useful interface is an iterator or async stream of `Frame` values with `sourceId`, `sequence`, `capturedAt`, image payload/reference, and optional source metadata. A replay adapter should implement the same interface as RTSP so demo validation does not depend on a live camera.

### Observation boundary

The proposal's observation shape is underspecified. `subjectId` cannot be derived from the current detector's bounding boxes without tracking, region-of-interest configuration, or a deterministic aggregation rule. `value` is ambiguous for a detection list, count, classification, occupancy, or state transition. `confidence` needs semantics when a count aggregates multiple detections.

A workable MVP observation should include:

* `schemaVersion`, `observationId`, `sourceId`, `capturedAt`, and `producedAt`
* `subjectId` or an explicit `subjectResolution: unresolved`
* `observationType` and typed `value`
* `confidence` plus a documented aggregation method
* `provider`, `modelId`, `modelVersion`, and optional frame reference

The adapter should preserve raw detections as diagnostic evidence while producing a normalized observation. Otherwise, changing from YOLO to a cloud model silently changes the mapper's input semantics.

### Event mapping boundary

The proposal treats mapping as a reusable rule step, but gives no rule language, input context, state model, or event semantics. The manifest example uses expressions such as `abs(observation.value - system.expectedCount) > 0`, but there is no definition of `system`, no configuration loader, no safe expression evaluator, and no rule test fixture.

The mapper must define:

* Stateless versus stateful rules, including previous-value storage.
* Event identity, deduplication, ordering, and replay behavior.
* Transition semantics: emit every observation, only changes, or debounced changes.
* Handling of unknown subjects and low-confidence observations.
* Typed payload and units, not only a free-form `value` field.

The sample `ProcessStateChanged` in the proposal is a state transition, whereas the current detector output is repeated frame-level evidence. A mapper that emits a state-change event for every sampled frame will create duplicates and make Fabric hydration noisy.

### Inference adapter boundary

The proposal assumes Foundry Local and Foundry can be swapped while retaining a stable contract. This is plausible at the application boundary, but unverified for this workload. Foundry Local on Azure Local documents OpenAI-compatible REST patterns and predictive AI support, but that does not establish that the selected YOLO model, image input format, preprocessing, postprocessing, confidence scores, batching, or model version are available identically in both runtimes.

The adapter should expose a workload-level method such as `infer(frame) -> RawInference`, not a provider-specific chat/completions shape. The adapter must own authentication, timeouts, retries, model readiness, health checks, and provider metadata. Model equivalence must be measured by event-level behavior, not assumed from endpoint compatibility.

### Fabric connector boundary

The proposal says the connector translates a process event into Eventstream records and that this is the only Fabric-specific integration point. The first half is plausible: Microsoft documents custom application sources for Eventstream and exposes Event Hubs, AMQP, and Kafka protocol details and sample code from the Eventstream UI. The second half is unverified because Digital twin builder mapping is documented around Fabric lakehouse tables, entity properties, time-series links, and flows.

The connector contract must answer:

* Which Eventstream source protocol is selected and why.
* Whether Eventstream lands data into an Eventhouse/KQL database, lakehouse, or another destination.
* How a process event becomes a source table with stable IDs and timestamps.
* Who creates and updates Digital twin builder mappings and schedules.
* Whether “visible ontology update” means a live event view, a refreshed mapped entity, a time-series property, or a dashboard query.
* How credentials are provisioned and rotated without putting connection strings in YAML or logs.

Until an end-to-end tenant test answers these questions, provide a local sink and captured payloads as first-class demo outputs. A successful Eventstream publish alone is not evidence that the ontology changed.

## Microsoft Fabric constraints

The following are current official-documentation findings as of 2026-09-15. They are platform evidence, but tenant behavior and preview changes still require validation.

### Eventstream

Microsoft documents Eventstream as a source/transform/destination feature and documents custom app or custom endpoint sources for application-produced events. The custom app documentation exposes connection details and sample code for Event Hubs, AMQP, and Kafka protocol tabs. This supports a connector that publishes records, but it leaves protocol choice, network reachability from Azure Local, authentication, schema, and throughput to the implementation.

Useful official references:

* [Eventstreams overview](https://learn.microsoft.com/fabric/real-time-intelligence/event-streams/overview)
* [Add a custom app source](https://learn.microsoft.com/fabric/real-time-intelligence/event-streams/add-source-custom-app)
* [Stream custom app events to a KQL database](https://learn.microsoft.com/fabric/real-time-intelligence/event-streams/stream-real-time-events-from-custom-app-to-kusto)

Inference: the Eventstream endpoint can be a transport boundary, but the proposal must name and test the landing destination and its schema. “Eventstream feeds Digital twin builder” is not a sufficient implementation contract.

### Digital twin builder

The official introduction requires a Fabric-enabled capacity, tenant enablement for Digital Twin Builder (preview), and no Autoscale Billing for Spark because Digital twin builder is incompatible with it. These are hard demo prerequisites, not optional operational polish.

The mapping documentation states that mappings select a source table from a Fabric lakehouse, use source columns to hydrate entity instances, and use exact property matches to link time-series data. It also states that entity types cannot be renamed after data is mapped, and modeled properties cannot be deleted or renamed or mapped from a different data type than originally defined. Entity type names have length and character restrictions.

The flow documentation states that mapping and contextualization operations run on demand or on schedules. It warns that a failed operation cancels downstream operations in the same flow and that repeated failures disable scheduled flows; it recommends separating operations into distinct flows. This makes the proposal's five-minute “visible update” target dependent on refresh schedule, mapping execution, capacity, and failure state, not only network latency.

Useful official references:

* [Digital twin builder introduction](https://learn.microsoft.com/fabric/real-time-intelligence/digital-twin-builder/tutorial-rti-0-introduction)
* [Mapping data to entity types](https://learn.microsoft.com/fabric/real-time-intelligence/digital-twin-builder/concept-mapping)
* [Digital twin builder flows](https://learn.microsoft.com/fabric/real-time-intelligence/digital-twin-builder/concept-flows)

The proposal's claim about preview constraints is directionally correct, but it should explicitly include tenant enablement, capacity, Autoscale Billing incompatibility, lakehouse source-table mapping, scheduled/on-demand operation behavior, immutable mapped names/types, and flow-disable behavior.

## Foundry Local on Azure Local versus Foundry cloud

### Confirmed distinctions

Official documentation describes Foundry Local on Azure Local as a preview workload deployed on an Azure Arc-enabled Kubernetes cluster running on Azure Local. It uses an inference operator, Model and ModelDeployment custom resources, gateway/API exposure, and authentication options including API keys, Entra ID, and Kubernetes service-account tokens. Deployment is currently by request during preview.

The requirements documentation calls out Kubernetes 1.29 or later, gateway API dependencies, certificate management, cluster capacity, model cache storage, and CPU/GPU sizing. The documented minimum worker profile is not a substitute for validating the selected model and throughput. Predictive AI is listed as supported, but the repository's Ultralytics YOLO weights are not proof of compatibility with the Foundry Local serving path.

Foundry Local on an end-user device is a different option from Foundry Local on Azure Local. Its documented local SDK and hardware assumptions should not be conflated with the Azure Local Arc extension. Foundry cloud deployments have different model availability, identity, network, quota, cost, and data-boundary properties.

Useful official references:

* [What is Foundry Local on Azure Local?](https://learn.microsoft.com/azure/azure-sovereign-clouds/private/foundry-local/overview)
* [Requirements for Foundry Local on Azure Local](https://learn.microsoft.com/azure/azure-sovereign-clouds/private/foundry-local/concept-requirements)
* [What is Foundry Local?](https://learn.microsoft.com/azure/foundry-local/what-is-foundry-local)

### Must be proven, not assumed

* Preview access is granted for the target subscription, region, and tenant.
* The target Azure Local instance and Arc-enabled Kubernetes cluster meet the required versions and can expose a secured inference endpoint.
* The chosen vision model can be deployed and invoked as predictive inference, including image transport and preprocessing.
* The model can meet the intended frame rate and latency on the actual CPU/GPU hardware.
* The cloud and local adapters can produce equivalent typed observations, even if raw model outputs differ.
* Network policy permits local publishing to the selected Fabric endpoint, with TLS and credential rotation.
* Model artifacts, caches, and updates work in the connected or disconnected operating mode intended for the demo.

## Risks and contradictions

### High-risk demo blockers

* **Fabric path ambiguity:** Eventstream ingestion and Digital twin builder hydration are described as one path, but the documented mapping source is a Fabric lakehouse table. Mitigation: build a minimal tenant experiment before coding a production connector.
* **Preview and tenant gates:** Digital twin builder requires enablement, capacity, and a specific Spark billing setting; Foundry Local on Azure Local requires preview access and a substantial cluster stack. Mitigation: record a signed-off environment checklist and a fallback local replay demo.
* **No prerecorded adapter:** The proposal's repeatable demo starts from a prerecorded clip, but the detector only accepts RTSP (`rtsp_yolo.py:40-47`, `125-145`). Mitigation: implement file replay first and test it without network or camera credentials.
* **Semantic mismatch:** The checked-in model output is generic object detection and the fixture is not factory data. Mitigation: use deterministic synthetic observations or a verified factory clip before claiming process-state correctness.
* **Duplicate state events:** Sampling frames and emitting state transitions are different operations. Mitigation: add debounce, state memory, event IDs, and replay tests.

### Security and privacy

RTSP credentials can appear in command lines and environment diagnostics; the current README shows credentials inline in an environment variable. Fabric Eventstream connection strings and WMS credentials must never be stored in the manifest, output JSONL, logs, or exception messages. Use secret references with a documented local-development mechanism and redact URLs. Define whether frames leave the site in cloud mode, and make the default behavior explicit.

The connector needs TLS verification, least-privilege identities, credential rotation, bounded retries, and protection against event injection. The event contract should avoid raw image or personally identifying data unless necessary.

### Reliability and operability

The current loop fails on a single unsuccessful frame read (`rtsp_yolo.py:148-150`) and has no reconnect or backpressure policy. It flushes each JSONL record (`rtsp_yolo.py:169-171`), which helps durability but does not make publication durable. There is no checkpoint, dead-letter path, queue bound, health endpoint, metrics, correlation ID, or structured error category.

For the MVP, require at least: counters for frames read/processed/dropped, inference latency, mapper events, sink successes/failures, and last successful publication; a bounded queue; retry with jitter for transient sink failures; and a local recorded sink for replay.

### Proposal contradictions and underspecified choices

* The proposal says the MVP is one line/process scenario and names line entities, but `manifest.yaml` is an aisle inventory/WMS scenario.
* The proposal says Fabric is mandatory and the connector targets Fabric, but the manifest targets `inventory-system`.
* The proposal says a simple configuration selects source, inference, ontology, and destination, but no configuration loader exists and the detector uses CLI/environment arguments.
* The proposal says cloud mode swaps only inference, but the infrastructure diagram shows a cloud path from capture and separate mapper/connector components. It is unclear whether capture and mapping are local, cloud, or independently deployable.
* The proposal says the connector is unchanged across inference modes, but it does not specify whether provider metadata is inside the stable event schema or discarded.
* The proposal's `subjectId` and `value` fields are insufficient for object detections and do not define identity tracking or count aggregation.
* The “under five minutes to a visible ontology update” target is not controlled by the process alone if Digital twin builder mapping is scheduled or on-demand.
* The out-of-scope list excludes production security and high availability, but the runtime choice introduces preview access, identity, TLS, Kubernetes, and data-boundary requirements that must be addressed even for a demo.

## Alternatives

### Alternative A: Contract-first local replay, then Fabric validation

Implement `Frame -> RawInference -> Observation -> ProcessEvent -> Sink` in one Python process. Use a deterministic fixture and local JSONL sink first; add an Eventstream payload sink only after schema validation. Manually configure one Fabric landing table and Digital twin builder mapping.

* Advantages: smallest change from current code, repeatable, debuggable, isolates contract risk from platform risk.
* Costs: does not prove Foundry Local on Azure Local early; Fabric may require a second ingestion/mapping path.
* Best use: recommended first slice.

### Alternative B: Eventstream-first cloud integration

Publish normalized events to a Fabric Eventstream custom app, land them in a supported Fabric destination, and manually configure Digital twin builder mapping. Keep local inference and cloud inference behind a common observation adapter later.

* Advantages: proves the mandatory Fabric dependency early and exposes tenant/network/schema blockers quickly.
* Costs: preview setup can dominate engineering; model/runtime portability remains untested; live platform failures obscure local contract defects.
* Best use: parallel environment spike, not the first application implementation.

### Alternative C: Edge-first Kubernetes deployment

Deploy capture, inference adapter, mapper, and local sink on Azure Local/Arc, then publish to Fabric. Use Foundry Local on Azure Local as the first inference provider.

* Advantages: validates the intended edge operating model, data boundary, and latency.
* Costs: highest prerequisite and access risk; cluster, GPU, gateway, TLS, model compatibility, and observability are all introduced at once.
* Best use: only after an access and model compatibility spike succeeds.

### Alternative D: Fabric-independent event contract with a connector replay harness

Treat Fabric as an external acceptance target. Generate versioned ProcessEvent records and replay them into a connector test harness, then manually upload or publish a small batch for ontology validation.

* Advantages: maximizes progress when tenant access is delayed and gives deterministic regression tests.
* Costs: risks overfitting an event schema that Fabric mapping cannot consume; does not prove streaming behavior.
* Best use: fallback and regression layer alongside Alternative A.

## Recommended first slice

Choose Alternative A with a small Alternative B environment spike. The first slice should demonstrate one complete local loop:

1. Replay a short clip or checked-in frame/detection fixture.
2. Normalize one observation, preferably a deterministic count or occupancy value with a documented subject.
3. Emit one debounced `ProcessEvent` with a stable ID and provider/model metadata.
4. Write the event to a local sink and validate it against a versioned JSON Schema.
5. Replay the same event to an Eventstream-compatible sink without changing the mapper.
6. Manually prove how the event lands in a Fabric table and how Digital twin builder maps and refreshes one entity or time-series property.

Do not make Foundry Local on Azure Local a prerequisite for this first slice. Add it only after the contract passes with a local deterministic provider and the platform readiness checklist is green.

## Experiments and revised success criteria

### Experiments

* **Contract replay:** feed the same fixture through two inference providers (deterministic fake and current YOLO adapter); verify identical `ProcessEvent` schema, with provider/model differences only in permitted metadata.
* **Event semantics:** replay repeated identical observations and a single state change; verify exactly one transition event, deterministic event ID, and documented behavior after restart.
* **Fabric landing:** publish ten records through the selected custom app protocol, confirm arrival in the chosen Fabric destination, inspect schema and timestamps, and record end-to-end delay.
* **Digital twin mapping:** map one stable entity ID and one time-series property, run on demand, then on schedule; record whether the visible update is immediate, scheduled, or unavailable.
* **Failure recovery:** stop the sink, generate events, restore it, and verify bounded retry, no silent loss, and duplicate behavior.
* **Runtime feasibility:** deploy or otherwise invoke the selected predictive model in each target runtime; record model format, input contract, cold start, p50/p95 latency, throughput, and confidence/output equivalence.
* **Security boundary:** confirm credentials are absent from logs and payloads, TLS is verified, and the cloud mode's frame/data egress is understood by the demo owner.

### Revised success criteria

* The repository has executable replay and RTSP adapters implementing the same frame contract.
* A versioned observation and process-event schema has fixtures, validation, and negative tests.
* A second provider changes only provider configuration and produces contract-valid events; semantic equivalence is measured rather than assumed.
* The Fabric experiment proves the complete landing-to-mapping path, including refresh timing and tenant prerequisites, or explicitly records the blocker.
* The demo has a local-only fallback that reaches a visible local sink in under five minutes.
* The live-camera smoke test covers disconnect and reconnect behavior.
* Logs and metrics identify source, event, provider, model, mapper decision, sink attempt, and outcome without exposing secrets.

## Proposed implementation sequence

1. Replace the current implicit JSONL shape with versioned Python data models for `Frame`, raw detection, `Observation`, and `ProcessEvent`.
2. Extract capture and inference from `run()` while preserving the current CLI as a compatibility wrapper.
3. Add file replay and deterministic fake inference; add schema fixtures and focused tests.
4. Implement a stateful/debounced mapper for one scenario and a local sink with replay and failure tests.
5. Reconcile `manifest.yaml` with the proposal: choose either line monitoring/Fabric or aisle inventory/WMS before adding adapters.
6. Run the Eventstream/Fabric landing experiment and document the actual protocol, destination, schema, credentials, and observed delay.
7. Configure one Digital twin builder entity and mapping manually; capture immutable naming/type decisions in documentation.
8. Implement the Fabric connector behind the sink interface, with bounded retry, idempotency, metrics, and redaction.
9. Prove Foundry cloud inference with a representative model and then prove Foundry Local on Azure Local access, deployment, endpoint, and model compatibility.
10. Rehearse the fallback and live-camera demos, run the user walkthrough, and revise the contract from observed variation effort.

## Open decisions requiring owner input

* Is the first scenario line monitoring for Fabric, or aisle inventory for WMS? The repository and proposal currently disagree.
* What exact Fabric destination is the source table for Digital twin builder mapping?
* Is the demo allowed to use manually configured Fabric mappings, or must the repository provision/configure them?
* What entity property is the first measurable value: count, occupancy, station state, or discrepancy?
* What model and hardware are available for Foundry Local on Azure Local, and has preview access been granted?
* What is the allowed cloud data boundary for frames, detections, and process events?

## Sources and evidence notes

Local evidence:

* `docs/mvp-design.md`
* `manifest.yaml:1-22`
* `apps/detect/rtsp_yolo.py:1-201`
* `apps/detect/README.md:1-17`
* `apps/detect/pyproject.toml:1-10`
* `apps/detect/detections.jsonl:1-2`
* `docs/core-idea.md:1`

Official Microsoft sources consulted:

* [Eventstreams overview](https://learn.microsoft.com/fabric/real-time-intelligence/event-streams/overview)
* [Add a custom app source to Eventstream](https://learn.microsoft.com/fabric/real-time-intelligence/event-streams/add-source-custom-app)
* [Stream custom app events to a KQL database](https://learn.microsoft.com/fabric/real-time-intelligence/event-streams/stream-real-time-events-from-custom-app-to-kusto)
* [Digital twin builder introduction](https://learn.microsoft.com/fabric/real-time-intelligence/digital-twin-builder/tutorial-rti-0-introduction)
* [Mapping data to entity types](https://learn.microsoft.com/fabric/real-time-intelligence/digital-twin-builder/concept-mapping)
* [Digital twin builder flows](https://learn.microsoft.com/fabric/real-time-intelligence/digital-twin-builder/concept-flows)
* [What is Foundry Local on Azure Local?](https://learn.microsoft.com/azure/azure-sovereign-clouds/private/foundry-local/overview)
* [Requirements for Foundry Local on Azure Local](https://learn.microsoft.com/azure/azure-sovereign-clouds/private/foundry-local/concept-requirements)
* [What is Foundry Local?](https://learn.microsoft.com/azure/foundry-local/what-is-foundry-local)
