<!-- markdownlint-disable-file -->
# Task Research: Add Foundry Local Support

Research into adding a Foundry Local backed perception workload to the tiger-poc factory perception pipeline, satisfying the "Edge mode runs inference through Foundry Local on Azure Local" runtime mode in docs/mvp-design.md.

## Task Implementation Requests

* Add Foundry Local support to the current environment
* Keep the existing Observation contract and downstream mapper/connector unchanged
* Prove the swap hypothesis: replace the perception component without touching the twin integration

## Scope and Success Criteria

* Scope: Foundry Local installation and runtime on this WSL/Ubuntu host, Python client integration, a `PerceptionWorkload` implementation backed by Foundry Local, model selection for image-based observations.
* Assumptions (to verify):
  * Foundry Local can run on Ubuntu/WSL without Azure Local hardware
  * A vision-capable model is available in the Foundry Local catalog
  * The existing `PerceptionWorkload` protocol is a sufficient seam
* Success Criteria:
  * Documented install path verified against this environment
  * A concrete `FoundryLocalWorkload` design emitting the existing `Observation` shape
  * Evidence on whether local hardware can run a suitable model
  * One recommended approach with rationale and rejected alternatives

## Outline

Pending subagent research.

## Potential Next Research

Pending subagent research.

## Research Executed

Pending subagent research.

## Key Discoveries

Pending subagent research.

## Technical Scenarios

Pending subagent research.
