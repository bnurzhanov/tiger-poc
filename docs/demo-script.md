---
title: Two-Cell Pallet Presence Demo
description: Two-minute partner demo of manifest-driven deployment across two physical camera setups.
---

## Goal

Show a Microsoft technology partner how the same application can deploy a
supported computer-vision use case to two differently arranged manufacturing
cells through configuration, without changing application code.

Both cells answer: "Is a pallet present in the monitored position?"

## Recording Prerequisites

* Two physical setups, each with one pallet position and one working RTSP camera
* Different camera angles and positions between setups
* One or more local developer machines with the application and validated inference models installed
* Two prepared manifests selecting camera sources, monitored regions, subject IDs, and `plantName` / `plantId` metadata
* One application instance per manifest, with separate local event outputs
* A side-by-side view of both camera feeds, monitored regions, occupancy states, and latest events

This is a planned demo, not a statement of current implementation readiness.
Assume Foundry Local and Azure Local are unavailable. Inference runs directly on
the local developer machines; Foundry cloud inference is not required.
Validate inference on occupied and empty views from both cameras before recording.
Keep camera credentials and connection endpoints off screen. Fabric and inventory
reconciliation are excluded. The two-minute duration is the video length, not an
installation-time claim.

## Two-Minute Script

| Time | Screen Action | Narration |
| ------ | --------------- | ----------- |
| 0:00-0:15 | Show the two physical setups and their distinct camera views. | "These cells need the same answer: is a pallet present at this position? Their cameras see the scene from different angles. We'll deploy the same application to both using different manifests." |
| 0:15-0:35 | Compare the manifests. Highlight camera source references, plant metadata, subject IDs, and monitored regions. | "Each manifest identifies the plant, selects its camera, and maps the monitored area to a stable position ID. These configurations describe the differences between the cells; the event contract and processing logic stay the same." |
| 0:35-0:50 | Launch the application once with each manifest on the local developer machines. Show both feeds and region overlays side by side, initially empty. | "We launch one instance per setup on our local dev machines. Each instance loads its configuration and starts inference against its physical camera." |
| 0:50-1:15 | Place a pallet in Cell A's region. Show its confirmed occupied state and local event while Cell B stays empty. | "Cell A observes a pallet and emits a pallet-presence event for its configured position. Cell B remains empty. The outputs stay associated with the correct setup." |
| 1:15-1:40 | Place a pallet in Cell B, then remove the pallet from Cell A. Keep both views visible as their states change independently. | "The second camera has a different viewpoint, but its workload answers the same question. Cell B becomes occupied, and Cell A returns to empty, using the same event format." |
| 1:40-2:00 | Compare the latest events and finish on both running workloads beside their manifests. | "Two physical setups, two manifests, one application. Both produce structured events locally from real camera inference, without changing application code between deployments. This POC demonstrates configuration-driven reuse for a validated vision use case." |

## Evidence To Capture

* Both workloads run concurrently and perform real camera inference
* Region overlays match each manifest and its camera viewpoint
* Confirmed occupancy changes produce `ProcessEvent` records with `observationType: PalletPresent`, boolean values, and the correct `sourceId` and `subjectId`
* Repeated unchanged observations do not produce repeated transition events
* No application-code edits occur between the two launches

Retain enough footage to show confirmation delays honestly; label any time cuts.
Do not present missing or unusable camera evidence as a confirmed empty position.
