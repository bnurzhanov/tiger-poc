---
title: Milestone 1 Validation Record
description: Software verification and outstanding physical evidence for the local two-cell perception milestone.
---

## Status

Milestone 1 is **not complete**. The local software is implemented, but the physical
pallet-model validation and two-camera recording remain open. The current user
trial uses a chair and emits `ObjectPresent`; it must not be presented as validated
`PalletPresent` inference. Two cameras are available, but only camera A's private
reference has been configured for this session.

## Implemented Surfaces

| Backlog Item | Software Delivered | Remaining Acceptance |
| --- | --- | --- |
| #10, configuration | Strict manifest loading, independent household configurations, paired local pallet templates | Calibrate both real views and supply a validated pallet model |
| #11, contracts | Successful-inference flag, normalized boxes, boolean schema checks, attribution and confidence semantics | Verify emitted physical pallet observations |
| #12, adapters | Isolated RTSP capture, paced local video replay, bounded queue, watchdog, normalized local YOLO, compatibility entry point | Verify both physical streams and concurrent performance |
| #14, presence | Initial confirmation, transition suppression, flicker reset, stale/failed evidence, reconnect rules | Validate policies against actual pallet observations |
| #15, local outputs | Schema validation, retries, recursive redaction, separate outputs, file ownership, counters | Verify real two-camera publication and archive evidence |
| #22, model suitability | Model label preflight and weight/runtime provenance | Pallet-capable model, occupied/empty views on both cameras, measured errors and throughput |
| #23, recording view | Loopback browser view, independent overlays/state/events, stale producer detection | Both real feeds visible and calibrated concurrently |
| #19, rehearsal | Launch commands, repeatable software gates, physical rehearsal checklist | Two-camera fault/recovery trial and two-minute recording |

No GitHub issues have been closed or redefined by this implementation.

## Verified Evidence

On 2026-09-15, the project's `uv` environment passed contract, manifest, mapper,
presence, adapter, sink, runner, and viewer tests. Tests include real OpenCV decoding
of a generated local video and a simulated hung-capture watchdog. Ruff and Python
compilation checks passed; see the
[runbook](../apps/detect/README.md#rehearsal-and-checks) for exact commands.

The VS Code integrated browser rendered the two-cell unavailable-state view and a
stacked narrow layout without horizontal overflow. No physical feed was available
for overlay validation. The standalone Playwright MCP could not start its configured
Chrome installation; the integrated browser was used for screenshots and DOM checks.

The bundled detector reports Ultralytics `8.4.152`, weights `yolo26n.pt`, SHA-256
`9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.
Its supported household labels include chair, bottle, cup, backpack, and suitcase.
It does not include pallet. Camera A's configured TCP port was reachable, but bounded
OpenCV probes failed authentication, including after private credential corrections.
No parent environment variable overrides the private file. No camera frames were
decoded and no physical occupancy events were produced. The camera workload was
stopped to avoid continued authentication retries; the viewer remains available at
<http://127.0.0.1:8765> for the next trial.

## Physical Evidence Checklist

* [ ] Both camera references configured privately and distinct
* [ ] Both streams decode continuously with independent regions
* [ ] Empty and occupied observations labeled by the operator for both viewpoints
* [ ] Selected model supports the actual target, with false positives and misses recorded
* [ ] A empty, B empty, A occupied, B occupied, A empty sequence archived
* [ ] Unchanged states produce no repeated events
* [ ] Camera loss, unusable frames, and recovery tested on both sources
* [ ] Hardware, placement, frame freshness, drops, throughput, and latency recorded concurrently
* [ ] Confirmation windows visible in footage, cuts labeled, endpoints and credentials excluded
* [ ] A new preparer reproduces launch and recording from the runbook
* [ ] Pallet-specific acceptance met, or scenario scope explicitly revised before closure

## Blockers And Owners

| Blocker | Owner | Impact | Next Action |
| --- | --- | --- | --- |
| No physical pallet or pallet-capable weights supplied | Demo owner | #22 and pallet-specific M1 acceptance cannot pass | Supply both, or explicitly approve a household-object milestone revision |
| Camera B reference not configured | Demo owner | Concurrent physical two-cell validation cannot run | Set `CAMERA_B_RTSP_URL` privately in `apps/.env` |
| Camera A rejects RTSP authentication | Demo owner | No decoded physical frames or trustworthy occupancy evidence | Verify the exact private URL in an RTSP player, fix account permissions or credential encoding, then relaunch |

Fabric work remains milestone 2 and is not required to resolve these local gates.
