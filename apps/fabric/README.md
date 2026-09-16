---
title: Fabric Digital Twin and Real-Time Intelligence
description: Ingest the canonical detect ProcessEvent contract and query confirmed object or pallet occupancy.
---

## Ownership And Contract

Python publishing and replay live in [apps/detect](../detect/README.md#fabric-publishing-and-edge-migration).
This directory owns only Fabric ingestion,
KQL queries, dashboard definitions and twin reference assets.

The source of truth is detect's [ProcessEvent schema](../detect/tiger_perception/schemas/process-event-v1.json),
[validator](../detect/tiger_perception/sinks.py) and
[production mapper](../detect/tiger_perception/mapping.py). Ingestion preserves all
required fields plus optional `observation`, `plantId` and `plantName` extensions.
Other extensions are not mapped. Raw `value` remains dynamic so non-presence scalar
events remain queryable, but only `PalletPresent` or `ObjectPresent` with an actual
boolean value and `unit == "boolean"` can update occupancy.

Plant metadata is optional on the wire. Occupancy queries join stable subject IDs
to reference tables instead of depending on payload plant fields. Seeded IDs match
the current detect manifests: cell A object, cell A pallet (root `manifest.yaml`
subject), cell B object, and cell B pallet. The two cell B manifests are
alternatives, not simultaneous owners of one output. Update the reference rows
when configuring other sources or subjects.

## Data Flow

```text
Detect Cameras -> Local JSONL -> Detect Fabric Relay
           |
           | (ProcessEvents JSON)
           v
Fabric Eventstream (Custom App source / Event Hubs)
           |
           +---> Fabric Eventhouse (KQL Database)
           |         |
           |         +---> Table: ProcessEventsRaw
           |         +---> Update policy: ConfirmedPresenceEvents
           |         +---> Materialized view: CurrentPositionOccupancy
           |         +---> Reference tables: Plants, Cells, MonitoredPositions
           |
           +---> Digital Twin Builder (Preview)
                     |
                     +---> Entities: Plant -> Cell -> MonitoredPosition
                     +---> Binding: last confirmed presence state
```

## Setup

### Create The Eventhouse

You need a Fabric workspace assigned to a
[Fabric-enabled capacity](https://learn.microsoft.com/en-us/fabric/enterprise/licenses#capacity).
Create the Eventhouse and its first KQL database in the Fabric portal:

1. Open the [Microsoft Fabric portal](https://app.fabric.microsoft.com), switch to
    the Fabric experience if needed, and select the target workspace.
2. Select **New item**, search for **Eventhouse**, and select **Eventhouse**.
3. Enter a name such as `tiger-poc-eventhouse`, and select **Create**. Names can
    contain letters, numbers, underscores, periods, and hyphens. Fabric creates the
    Eventhouse and a default child KQL database with the same name.
4. Use the default database for this POC, or create a separate database by selecting
    **+** under **KQL Databases**, entering a name such as `tiger-poc`, selecting
    **New database**, and then selecting **Create**.
5. Select the database and open its automatically created embedded KQL queryset.
    Use this query environment to run the setup scripts in the next section.

An Eventhouse can contain multiple KQL databases that share its capacity and
resources. See the Microsoft Learn instructions for
[creating an Eventhouse](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/create-eventhouse)
and [creating a KQL database](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/create-database)
for the current portal workflow.

### Prepare The Database

Use a new KQL database for this revised setup. Execute individual management
commands in order, before sending events:

> [!IMPORTANT]
> These files contain separate commands, not a single query to run as a batch.
> In the default or standalone Fabric queryset, highlight one complete command
> block and select **Run**. Run can execute only the current block; pasting a file
> into the editor does not mean all its commands have executed. Wait for success
> after every command and stop on errors. Keep the same database selected.

1. Execute the numbered blocks in [01_create_tables.kql](kql/01_create_tables.kql)
    individually, from top to bottom. Blocks 1-6 create raw/reference tables,
    JSON mapping and the ingestion-time policy. Select all quoted mapping lines
    together as part of block 2. At block 7, confirm `.show tables` lists
    `ProcessEventsRaw`, `Plants`, `Cells` and `MonitoredPositions` before seeding.
    Run seed blocks 8-10 once each, selecting the command and all its CSV rows
    together. Run count queries 11-13 separately; in a fresh database seeded once,
    expect 1 plant, 2 cells and 4 monitored positions.
2. Execute each command in [02_update_policy.kql](kql/02_update_policy.kql)
    separately, in order, to create the typed presence
     table, transactional update policy and aggregation-only materialized view.
    Select each function or view definition with its complete brace-delimited
    body, and the update-policy command with its JSON string.
     Wait for the returned `.create async materialized-view` operation to complete
     before continuing to twin bindings and query validation; until it finishes,
     `CurrentPositionOccupancy` can be unavailable even though the command returned.
3. Create an Eventstream Custom App source, or connect the Event Hubs source
     provisioned by [the optional infrastructure](../../infra/digital-twin-poc/README.md).
    For Event Hubs consumer authentication, follow that guide's
    [Fabric consumer setup](../../infra/digital-twin-poc/README.md#fabric-consumer-authentication);
    the producer identity and its sender role do not authorize Fabric to read.
     Configure the KQL destination as `ProcessEventsRaw` and map the original top-level
     JSON fields. For direct JSON ingestion, select `ProcessEventsRaw_JSON_Mapping`.
     Verify Eventstream's destination mapping too; a named KQL mapping alone does not
     configure the Eventstream UI.
4. Configure the [detect relay](../detect/README.md#fabric-publishing-and-edge-migration)
     and send validated events. Event Hubs uses the standard JSON event body; no
     detector contract change is needed in the Bicep resources.
5. Run [03_sample_queries.kql](kql/03_sample_queries.kql) and inspect both presence
     types, enriched identities, timestamps and observed transition state.

Existing databases need an explicit migration: these scripts are not destructive
or fully idempotent upgrades. They do not remove legacy tables or views. Old raw
data is not backfilled by the new update policy. If needed, run
`.set-or-append ConfirmedPresenceEvents <| ExtractConfirmedPresence()` once after
creating the policy, avoiding overlapping live ingestion; deduplicate replayed
event IDs. The materialized view backfills from `ConfirmedPresenceEvents`, not raw
history. Update dashboard bindings to the new table and view names.

### Recover From A Missing Table During Setup

`BadRequest_TableNotExist` for `MonitoredPositions` while running the seed command
means the table did not exist in the executing database at that time. A likely
cause is running only the final `.ingest inline` block without first executing
the `.create table` block. The error alone does not establish an Eventstream
configuration problem or a database mismatch.

1. In the queryset, confirm the selected database matches the database named in
    the error, then run `.show tables` as a separate command.
2. If `MonitoredPositions` is missing, highlight and execute its complete
    `.create table MonitoredPositions (...)` block (block 6). Wait for success.
    If creation fails, resolve that error before attempting ingestion again.
3. Run this command separately to confirm the schema exists:

    ```kusto
    .show table MonitoredPositions schema as json
    ```

4. Run the corresponding count query before seeding. If the table is empty and
    the earlier seed failed, execute its seed block once, then verify the count.
    If rows already exist, inspect them before deciding whether data is missing.
5. Resume any remaining setup blocks individually, verifying each result.

> [!WARNING]
> `.ingest inline` appends rows. Do not rerun successful seeds or the entire setup
> blindly during recovery; duplicate reference rows can multiply joined results.

See [Microsoft Learn's KQL queryset guide](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/kusto-query-set)
for data-source selection and query execution in the Fabric portal.

### Configure Twin And Dashboard Views

Use [ontology_definition.json](digital_twin/ontology_definition.json) and
[twin_instances.json](digital_twin/twin_instances.json) as design references for
manual setup. They are not validated official Fabric import formats. Bind
`MonitoredPosition.positionId` to `CurrentPositionOccupancy.subjectId`, and map
`isOccupied`, `confidence`, `observationType` and `capturedAt` as specified. Do not
bind arbitrary raw events to occupancy or initialize an unobserved position empty.
Null seed values mean unknown; omit those initial properties if the UI rejects null.

The [dashboard JSON](dashboards/fabric_realtime_dashboard.json) is a tile/query
blueprint, not a verified import package. Configure the tiles against your KQL
database. [The Power BI M query](dashboards/powerbi_directquery_kql.m) uses the same
view and reference joins. Connect using DirectQuery, select Transform Data, and
replace the query in Power Query's Advanced Editor with the full M expression,
updating its endpoint and database placeholders. Connector query fields accept
KQL, not the full M expression. Configure Power BI automatic page refresh and
Fabric dashboard refresh separately at supported intervals. Refresh frequency
depends on service/capacity settings and query duration, not a guaranteed
five-second SLA. See the [Power Query connector guidance](https://learn.microsoft.com/en-us/power-query/connectors/azure-data-explorer)
and [Power BI refresh limits](https://learn.microsoft.com/en-us/power-bi/create-reports/desktop-automatic-page-refresh).

## State And Delivery Semantics

* Occupancy is the last confirmed state by `capturedAt`, not current camera health.
    Event silence must never change occupancy to empty. Detect status files remain
    the local availability source; they are not ingested by these queries.
* Occupied confidence is detector evidence; empty confidence is 0.0 and not an
    estimated probability. Preserve zero-confidence empty events.
* Unobserved positions have no occupancy row and are excluded from confirmed-state
    KPIs. Seeded references do not imply that a camera has reported a state.
* Each subject has one configured source owner. Equal capture timestamps with
    conflicting values do not define a deterministic winner; avoid competing
    producers for one subject.
* Retried/replayed event IDs can appear more than once in raw ingestion. Timeline
    queries deduplicate by `eventId`; occupancy aggregates by subject and capture time.
* Latency uses the database's `ingestion_time()`, not a fabricated payload field.
    Synthetic demo timestamps are unsuitable for measuring live latency.

## Validation

From the repository root:

```bash
uv run --project apps/detect --extra fabric pytest apps/detect/tests/test_fabric.py apps/detect/tests/test_fabric_contracts.py -q
```

Local tests cover canonical validation, publisher behavior, JSON mappings, manifest
identity alignment, and query references. They do not execute KQL or validate
Fabric UI/import compatibility. Before live use, execute the setup and queries in
a test database and confirm that non-presence events leave occupancy unchanged,
both presence types update correctly, and replay does not duplicate timeline rows.
