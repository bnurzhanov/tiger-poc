<!-- markdownlint-disable-file -->
# Planning Log: Portable Factory Perception MVP

## Discrepancy Log

Gaps and differences identified between the supplied research, repository evidence, and the implementation plan.

### Unaddressed Research Items

No current unaddressed research item remains for the requested validation scope. The failure-recovery procedure is explicit in Step 3.2, and all plan-to-details ranges align with the corresponding details sections.

### Plan Deviations from Research

No current plan deviation remains. The scenario gate, Fabric destination gate, provider-equivalence test, bounded queue policy, Phase 4 execution ordering, sink recovery procedure, and deferred Foundry Local scope align with the research recommendations.

### Resolved Discrepancies

* DR-01 resolved: The details now explicitly require stopping the sink, generating events, restoring it, and verifying bounded recovery without silent loss in Step 3.2.
* DR-02 resolved: The plan's 13 details ranges match the corresponding Step 1.1 through Step 6.2 sections, including Step 4.2 at details Lines 205-222.
* DR-03 resolved: Step 6.1 now requires isolated validation failures to be fixed and rerun, and requires unresolved blockers to record an owner, evidence, impact, and recommended next planning action.

## Implementation Paths Considered

### Selected: Contract-first local replay with a parallel Fabric spike

* Approach: Build typed contracts, deterministic replay, fake and YOLO adapters, a stateful mapper, and a local sink first; validate Eventstream landing and Digital twin builder mapping in parallel; add the selected Fabric sink afterward.
* Rationale: It isolates application semantics from tenant and preview risks, preserves a runnable offline demo, and directly addresses the highest-risk duplicate-event and contract gaps.
* Evidence: .copilot-tracking/research/2026-09-15/portable-factory-perception-mvp-research.md (Recommended first slice and Proposed implementation sequence)

### IP-01: Eventstream-first cloud integration

* Approach: Publish to Fabric before completing local replay and mapper tests.
* Trade-offs: Finds tenant blockers early, but platform failures obscure local contract defects and make deterministic regression harder.
* Rejection rationale: Use as the parallel spike, not as the application implementation order.

### IP-02: Edge-first Foundry Local deployment

* Approach: Deploy the pipeline on Azure Local/Arc and use Foundry Local as the first inference provider.
* Trade-offs: Tests the intended edge topology, but introduces preview access, Kubernetes, gateway, TLS, hardware, and model compatibility risks simultaneously.
* Rejection rationale: The research explicitly identifies these prerequisites as unverified; they must not gate the local MVP.

### IP-03: Fabric-independent connector replay harness only

* Approach: Build versioned ProcessEvent records and replay them into a connector harness without a live Fabric experiment.
* Trade-offs: Maximizes offline progress, but risks choosing a schema that cannot feed the actual Fabric landing table.
* Rejection rationale: Retain captured payload replay as a supporting test mechanism, while still requiring a tenant landing experiment.

## Suggested Follow-On Work

* WI-01: Add live RTSP resilience — implement reconnect, bounded queues, backpressure, and health metrics after replay contracts stabilize (medium; depends on Phase 2).
* WI-02: Provision Fabric mappings as code — investigate repository-managed Fabric item/configuration artifacts after manual landing-to-mapping behavior is proven (medium; depends on Phase 4).
* WI-03: Prove provider equivalence — benchmark Foundry cloud and Foundry Local with representative image input and event-level comparison (high; depends on platform access and Phase 1 contracts).
* WI-04: Add deployment artifacts — create container, Azure Local/Arc, or cloud deployment assets only after the runtime topology and provider are selected (medium; depends on WI-03).
