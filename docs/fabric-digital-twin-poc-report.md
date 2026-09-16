---
title: Factory Edge Perception to Microsoft Fabric POC Report
description: Historical POC report with current detect execution commands and artifact ownership.
---

**Date:** 2026-09-15  
**Workload:** Portable Factory Perception MVP (Milestone 2 - Microsoft Fabric & Digital Twin Integration)  
**Branch:** `feature/fabric-digital-twin-poc`  

---

## Executive Summary

> [!NOTE]
> Architecture and service verification claims below describe the original POC.
> For current contracts, setup limitations and supported commands, use the
> [detect guide](../apps/detect/README.md) and [Fabric guide](../apps/fabric/README.md).

This document details the research, architecture planning, and implementation of connecting edge manufacturing perception workloads to **Microsoft Fabric Real-Time Intelligence**. 

The current implementation provides a separate relay for completed `ProcessEvent`
JSONL files and synthetic demos. Fabric assets describe confirmed occupancy in a
`Plant` -> `Cell` -> `MonitoredPosition` hierarchy. Twin and dashboard JSON files
are manual configuration references, not verified import packages. Live Fabric
delivery, twin updates and report latency remain unverified; DirectQuery and
refresh settings do not guarantee sub-second or five-second end-to-end updates.

---

## 1. Research & Architectural Decisions

### 1.1 Ingestion & Transport Connectivity
* **Standardization:** Process observations adhere to the versioned `process-event-v1.json` schema, encapsulating `eventId`, `sourceId`, `subjectId`, `observationType: PalletPresent`, boolean `value`, `confidence`, timestamps, and plant/cell metadata.
* **Hybrid Connectivity Pattern:** Edge nodes communicate with Fabric through a dual-mode `FabricEventstreamSink`:
  1. **Production Mode:** Event Hubs protocol through a Fabric Custom App source connection string or an Azure Event Hubs namespace.
  2. **Dry-Run / Local Mode:** Validates schema, logs structured output to console, and mirrors events to local JSON Lines (`.jsonl`) files when cloud credentials are not present.

### 1.2 Fabric Eventhouse & Digital Twin Model
* **Eventhouse / KQL Database:** 
  - `ProcessEventsRaw`: Ingests streaming payloads.
  - `ConfirmedPresenceEvents`: Typed presence events populated by a transactional update policy.
  - `CurrentPositionOccupancy`: Materialized view maintaining the latest confirmed boolean occupancy per position using `arg_max(capturedAt, *)`.
  - Static Reference Hierarchy: `Plants` -> `Cells` -> `MonitoredPositions`.
* **Digital Twin Builder (Preview):** 
  - The reference ontology links `Plant` `containsCell` `Cell`, and `Cell` `monitorsPosition` `MonitoredPosition`.
  - Bind `CurrentPositionOccupancy.subjectId` to `MonitoredPosition.positionId`; map confirmed `isOccupied`, `confidence`, `observationType`, and `capturedAt` (to `lastObservedTimestamp`). Raw events are not a current-state binding.

### 1.3 Real-Time Visualization
* **Fabric Real-Time Dashboard:** Tile/query blueprint for confirmed position counts, occupancy percentage, last confirmed state, transitions, and ingestion latency. Configure refresh at an interval supported by the service; the blueprint is not a verified import package or latency guarantee.
* **Power BI DirectQuery (KQL):** M query script for Power BI Desktop with Automatic Page Refresh (APR).

---

## 2. Directory Structure & Artifact Inventory

The workspace is organized into clean functional modules:

```text
tiger-poc/
├── docs/
│   ├── mvp-design.md                     # Base MVP specification
│   ├── demo-script.md                    # 2-minute partner demo script
│   └── fabric-digital-twin-poc-report.md # Research, planning & implementation report (this document)
│
├── infra/
│   └── digital-twin-poc/                 # Infrastructure as Code (Bicep)
│       ├── main.bicep                    # Event Hubs namespace, topics & Managed Identity orchestration
│       ├── main.bicepparam               # Parameter file for dev environment
│       ├── types.bicep                   # Shared Bicep type definitions
│       ├── modules/
│       │   ├── eventhub.bicep            # Event Hubs, sender RBAC & optional consumer SAS policy
│       │   └── identity.bicep            # User-Assigned Managed Identity
│       └── README.md                     # IaC deployment guide
│
└── apps/
    ├── detect/                           # Detection, canonical contracts and optional Fabric relay
    │   ├── pyproject.toml                # Detection dependencies and optional fabric extra
    │   ├── README.md                     # Camera execution and Fabric relay guide
    │   ├── manifests/
    │   │   ├── cell-a.yaml               # Cell A household-object trial
    │   │   ├── cell-b.yaml               # Cell B household-object trial
    │   │   └── cell-b-pallet.yaml        # Cell B pallet model template
    │   ├── tiger_perception/
    │   │   ├── __init__.py
    │   │   ├── contracts.py              # Typed ProcessEvent and Observation dataclasses
    │   │   ├── presence.py               # Stateful presence rule (confirmation windows & suppression)
    │   │   ├── sinks.py                  # Canonical validation and LocalJsonlSink
    │   │   ├── fabric.py                 # Fabric publisher, JSONL relay and multi-cell demo
    │   │   ├── replay.py                 # Local event replay
    │   │   ├── runner.py                 # Manifest-driven pipeline runner
    │   │   └── schemas/
    │   │       └── process-event-v1.json # ProcessEvent JSON Schema
    │   └── tests/                        # Full unit test suite (contracts, rules, sinks, replay)
    │
    └── fabric/                           # Microsoft Fabric & Real-Time Intelligence Artifacts
        ├── README.md                     # Step-by-step Fabric setup guide
        ├── kql/
        │   ├── 01_create_tables.kql      # Raw streaming table, reference tables (Plant/Cell/Position)
        │   ├── 02_update_policy.kql      # Materialized views & continuous state aggregations
        │   └── 03_sample_queries.kql     # Current state, transition history, and latency queries
        ├── digital_twin/
        │   ├── ontology_definition.json  # Digital Twin Builder ontology (Plant -> Cell -> Position)
        │   └── twin_instances.json       # Seed twin instance graph
        └── dashboards/
            ├── fabric_realtime_dashboard.json # Manual tile/query blueprint; refresh is service-dependent
            └── powerbi_directquery_kql.m      # Power BI DirectQuery KQL connector & setup
```

---

## 3. Implementation Verification & Test Results

### 3.1 Unit Testing
The original POC recorded nine passing tests for its former standalone prototype.
That historical result is not a verification of the current implementation.
The supported suite in [apps/detect/tests](../apps/detect/tests) covers contracts,
presence rules, Fabric publishing and multi-cell replay. After the review fixes,
96 tests passed locally, including root-manifest identity coverage, historical
demo timestamps, relay error diagnostics and both publisher authentication paths.
Live Fabric delivery and KQL execution remain unverified.

### 3.2 Bicep Compilation & IaC Linting
Bicep templates compile cleanly to ARM JSON without warnings:

```bash
bicep build infra/digital-twin-poc/main.bicep -> Success (0 diagnostics)
```

---

## 4. Operational Execution Instructions

### 4.1 Infrastructure Deployment (Azure CLI & Bicep)

Follow the [infrastructure deployment guide](../infra/digital-twin-poc/README.md#deployment-commands).
It captures `DEPLOYMENT_NAME` once and reuses it for deployment and output lookup.
The templates create Event Hubs, a user-assigned producer identity with hub-scoped
Data Sender access, and an optional Listen-only consumer policy. Outputs contain
only nonsecret configuration, not connection strings. Host attachment and Fabric
consumer configuration remain separate steps.

### 4.2 Running Detection And Publisher Tests

Run unit tests across edge contracts, presence evaluation rules, sinks, and replay generators:

```bash
uv run --project apps/detect --extra fabric pytest apps/detect/tests
```

### 4.3 Running Edge Simulation (Dry-Run Mode)

Simulate cell A object and cell B pallet presence transitions locally with schema
validation and JSONL trace output:

```bash
# Dry-run to local file and stdout logs
uv run --directory apps/detect --extra fabric python -m tiger_perception.fabric \
  --demo --dry-run \
  --output ../../data/simulation.jsonl \
  --interval 1.0 \
  --iterations 1
```

### 4.4 Running Live Ingestion to Microsoft Fabric

Before sending events, complete the Fabric database and destination setup in
section 4.6. Configure the namespace hostname and hub name using the
[producer authentication steps](../infra/digital-twin-poc/README.md#producer-authentication).
On an Azure host, attach the provisioned identity and set `AZURE_CLIENT_ID` to its
client ID. Locally, use a developer identity with a separate sender role assignment.
Then send the demo through Event Hubs to the configured Fabric Eventstream:

```bash
# Run live streaming simulation
uv run --directory apps/detect --extra fabric python -m tiger_perception.fabric \
  --demo \
  --live-fabric \
  --interval 2.0 \
  --iterations 5
```

### 4.5 Running Edge Pipeline with Workload Manifests

Launch these camera workloads in separate terminals. They write local JSONL;
Fabric publication is a separate relay step, not a camera-runner flag.

```bash
# Launch Cell A workload
uv run --project apps/detect apps/detect/rtsp_yolo.py \
  --manifest apps/detect/manifests/cell-a.yaml --env-file apps/.env

# Launch Cell B workload
uv run --project apps/detect apps/detect/rtsp_yolo.py \
  --manifest apps/detect/manifests/cell-b.yaml --env-file apps/.env
```

After stopping the workloads, relay their completed event files with the destination
configured in the process environment:

```bash
uv run --directory apps/detect --extra fabric python -m tiger_perception.fabric \
  --input ../../data/cell-a/events.jsonl ../../data/cell-b/events.jsonl \
  --live-fabric
```

### 4.6 Setting up Microsoft Fabric Eventhouse & Digital Twin

Use the [maintained Fabric setup guide](../apps/fabric/README.md#setup) for the
command order, consumer authentication, destination mapping and migration caveats.
Create `ProcessEventsRaw`, reference tables `Plants`, `Cells`, `MonitoredPositions`,
then `ConfirmedPresenceEvents` and `CurrentPositionOccupancy` before publishing.

Use the twin assets for manual configuration, binding
`CurrentPositionOccupancy.subjectId` to `MonitoredPosition.positionId`. Map
`isOccupied`, `confidence`, `observationType`, and `capturedAt` to the corresponding
properties (`capturedAt` becomes `lastObservedTimestamp`). Preserve unknown initial
state; neither raw events nor missing events establish current occupancy.

Build Fabric dashboard tiles manually from the JSON blueprint. For Power BI,
connect using DirectQuery, choose Transform Data, and paste the full M expression
into Power Query's Advanced Editor, not the connector's KQL query field. Configure
each product's refresh independently at a supported interval and verify actual
behavior after publishing. Five seconds is an optional target subject to service,
capacity, administrator settings and query duration, not a guaranteed SLA.
