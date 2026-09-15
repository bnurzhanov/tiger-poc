<!-- markdownlint-disable-file -->
<!-- markdown-table-prettify-ignore-start -->
---
title: Two-Milestone Backlog Refresh Analysis
description: Approved scope and existing issue assessment for the local demo and Fabric digital twin backlog.
---

## Scope And Approval

Repository: dkirby-ms/tiger-poc.
Sources: docs/mvp-design.md and docs/demo-script.md as revised in this session.
Follow github-backlog-planning.instructions.md for field conventions and content sanitization.

The user approved two GitHub milestones, three new issues, updates to the eleven active issues, milestone assignments, and the scope update to security-labeled #18. No closures, reassignments, code changes, commits, or pushes are authorized by this operation.

Both milestones use ordinary local developer machines. M1 proves two concurrent physical-camera workloads with independent local presence events. M2 adds the Fabric digital twin representation and end-to-end updates without changing inference. Foundry and Azure Local are post-MVP.

## Found And Suggested Issue Fields

All issues #10 through #20 are open and have no milestone. #15 is assigned to dkirby-ms; all other active issues are unassigned. Preserve these states and assignees. Existing labels are retained. Closed issues #1 through #8 are historical and receive no changes.

| Issue | Found title | Labels | Assessment and proposed action | Target |
| --- | --- | --- | --- | --- |
| #10 | Define the first factory scenario and event contract | enhancement, planning, priority:high | Match: specify the selected pallet scenario and executable two-manifest configuration | M1 |
| #11 | Define versioned data contracts for observations and process events | enhancement, contracts, priority:high | Match: retain implemented contracts and verify presence, availability, and metadata coverage | M1 |
| #12 | Split capture and inference into reusable adapters | enhancement, adapters, priority:high | Match: prioritize physical RTSP and local inference; keep replay/fakes as test tools | M1 |
| #13 | Compare inference providers using the same replay | enhancement, inference, priority:medium, testing | Preserve as explicitly post-MVP, not a demo dependency | None |
| #14 | Turn observations into debounced process events | enhancement, events, priority:high | Match: region presence confirmation, unknown/unavailable semantics, and state isolation | M1 |
| #15 | Add a schema-validating local JSONL sink | enhancement, priority:high, reliability | Match: reuse existing sink and verify separate outputs from concurrent instances | M1 |
| #16 | Confirm how events land in Fabric Eventstream | fabric, priority:high, spike | Match: validate dev-box publication, both identities, and the actual landing path | M2 |
| #17 | Confirm Digital twin builder mapping and refresh timing | digital-twin, fabric, priority:high, spike | Match: extend mapping validation to both cells, relationships, and inspectable state | M2 |
| #18 | Build the Fabric sink using the confirmed transport | enhancement, fabric, priority:high, security | Match: preserve security/reliability criteria; replace provider comparison with unchanged local processing | M2 |
| #19 | Rehearse and validate the complete local and live-camera paths | documentation, priority:high, testing | Match: physical two-cell rehearsal and two-minute recording, not optional live smoke test | M1 |
| #20 | Assess readiness for Foundry cloud and Foundry Local | azure-local, foundry, priority:medium, spike | Preserve as explicitly post-MVP, not an MVP access gate | None |
| New model validation | None | inference, testing, priority:high | Distinct: physical-viewpoint/model suitability evidence is not adapter extraction or provider comparison | M1 |
| New viewer | None | enhancement, priority:high | Distinct: build the side-by-side tool that rehearsal consumes | M1 |
| New Fabric walkthrough | None | fabric, digital-twin, testing, priority:high | Distinct: integrated physical-to-twin evidence after landing, mapping, and sink implementation | M2 |

## Execution Decisions

* Create M1: Local Two-Cell Demo and M2: Fabric Digital Twin Representation without invented due dates.
* Use existing repository labels only; label names verified through the GitHub labels tool.
* Put explicit milestone scope and prerequisites in each active issue body.
* Keep #13 and #20 open with post-MVP titles and no milestone; do not repurpose their original goals.
* Do not close #11 or #15 based solely on local implementation-plan checkmarks. Existing code must be reused and verified against the refined criteria.
* Publish self-contained criteria and public repository references, never internal tracking paths or temporary planning IDs.
* Write operations use GitHub CLI because available GitHub tools expose read operations only. Execute sequentially and verify returned fields.

## Planned Verification

Validate the payload structure and prohibited references before writes. Verify each remote title, body, milestone, labels, assignee, and open state after applying it. Verify milestone descriptions and issue totals: M1 eight issues, M2 four issues, two post-MVP issues without milestones. Preserve historical closed issues.

<!-- markdown-table-prettify-ignore-end -->