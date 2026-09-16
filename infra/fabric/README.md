---
title: Signed-In Fabric Bootstrap
description: Create the Tiger Fabric items from the merged application artifacts using an interactive user identity.
---

## Scope

[deploy.py](deploy.py) creates or resumes a deployment in an existing Fabric
workspace. It uses your Azure CLI user login, not a service principal. No Azure
resources, capacity, workspace, tenant settings, credentials, or role assignments
are created. Provisioning consumes capacity; flow execution can incur additional
Spark usage.

The bootstrap extends the artifacts from PR #25:

* [KQL schema and reference seeds](../../apps/fabric/kql/01_create_tables.kql)
* [Presence update policy and occupancy view](../../apps/fabric/kql/02_update_policy.kql)
* [Twin design reference](../../apps/fabric/digital_twin/ontology_definition.json)
* [Reference instances](../../apps/fabric/digital_twin/twin_instances.json), checked against the KQL seeds by tests
* [Existing detect publisher and relay](../../apps/detect/README.md#fabric-publishing-and-edge-migration)

The optional [Azure Event Hubs infrastructure](../digital-twin-poc/README.md) is
an alternative transport, not a prerequisite for this Custom App source setup.
The bootstrap does not create a second publisher or use the standalone jeep CSV.

> [!IMPORTANT]
> This implementation has offline tests, not a successful live Fabric deployment.
> Public preview definitions are available, but a supported
> `DigitalTwinBuilderFlow` job type has not been established. `apply` creates
> definitions and reference data; it does not initialize twin instances or run
> mappings. Eventstream connection details and flow execution still require
> portal steps unless the tenant's supported API contract is confirmed.

## Prerequisites

1. Use a new or manually cleared workspace on an active, supported Fabric capacity.
   Have Contributor or higher access. The script checks capacity assignment, not
   its current health, region support, or your effective permissions.
2. Ask your Fabric administrator to enable Digital twin builder (preview) for
   your user. Its flows are not compatible with Autoscale Billing for Spark.
3. Install `uv` and Azure CLI, then sign in interactively to the workspace tenant:

   ```bash
   az login --tenant "<tenant-id>" --allow-no-subscriptions
   ```

Complete browser/device authentication yourself. Never put tokens or connection
strings into the config, manifests, source control, or chat. Application-only
Azure CLI sessions are rejected. Credentials are requested separately for Fabric,
OneLake, and the workspace's KQL endpoint.

## Plan And Apply

Run from the repository root:

```bash
uv run infra/fabric/deploy.py plan
uv run infra/fabric/deploy.py apply --workspace "<workspace-id>" --tenant "<tenant-id>"
uv run infra/fabric/deploy.py status --workspace "<workspace-id>" --tenant "<tenant-id>"
```

`uv` resolves the script's declared dependencies. `plan` itself makes no cloud or
authentication calls; the first `uv` invocation can download dependencies.
It validates local artifacts and prints item names and a deployment fingerprint.
No publisher starts during provisioning. `status` reads resource inventory,
local checkpoints, raw-event count, and latest capture time; it is not a complete
health check for Eventstream, OneLake, mappings, or scheduled jobs.

[config.json](config.json) controls the prefix, canonical artifact directory,
allowed presence types for twin history, and OneLake target latency. Paths are
relative to the config file. `--config` selects another config. The default
`tiger` prefix creates nine explicitly managed items:

| Item | Name |
| --- | --- |
| Eventhouse | `tiger_events` |
| KQL database | `tiger_events_db` |
| Source lakehouse | `tiger_reference` |
| Twin backing lakehouse | `tiger_twin_data` |
| Eventstream | `tiger_ingest` |
| Digital twin builder | `tiger_twin` |
| Reference mapping flow | `tiger_reference_flow` |
| Hierarchy contextualization flow | `tiger_relationships_flow` |
| Presence time-series mapping flow | `tiger_timeseries_flow` |

Fabric may also create dependent system items. The script does not delete them.

## Data And Model

```text
Detect JSONL -> existing detect relay -> Eventstream Custom App source
  -> ProcessEventsRaw (dynamic value, original timestamps and IDs)
  -> ExtractConfirmedPresence transactional update policy
  -> ConfirmedPresenceEvents
       -> CurrentPositionOccupancy (latest capturedAt per subject)
       -> OneLake availability -> source lakehouse shortcut
            -> MonitoredPosition time-series mapping

KQL reference seeds -> KQL reference tables and source lakehouse Delta tables
  -> Plant, Cell, MonitoredPosition mappings -> hierarchy contextualization
```

The schema compiler preserves the shipped multiline commands and JSON mapping.
It excludes inspection and append-only seed blocks, translates table creation to
`.create-merge table`, and uses `.create-or-alter materialized-view`. The definition
API permits only a subset of KQL management commands. In particular, ingestion-time
policy is applied separately through the KQL endpoint after database creation and
before Eventstream creation. Unsupported commands fail with
`ScriptContainsUnsupportedCommand`, even when valid in a KQL queryset.
Because the destination is a new, empty database, the view is created synchronously
without a historical backfill. This is not a migration path for existing event history.

Reference data comes from the KQL CSV seeds: one plant, two cells, four positions.
Retries replace only these owned reference tables, using `.set-or-replace` in
KQL and overwrite loading in the source lakehouse. No raw or confirmed event table
is replaced. Reference metadata stays aligned with the shipped instance JSON.

The renderer converts the design reference into public Fabric definition parts.
It adds `plantId` to Cell and `cellId` to MonitoredPosition for hierarchy joins.
Static identities use the existing stable IDs. Time series link `subjectId` to
`positionId`, map `capturedAt` to `Timestamp`, and retain `eventId`, occupancy,
confidence, observation type, and last-observed timestamp. Unobserved occupancy
is omitted, not initialized to false.

The design reference's `CurrentPositionOccupancy` binding describes latest state.
This deployment keeps that KQL view for operational queries and maps the validated
`ConfirmedPresenceEvents` table as twin history instead. It does not treat a
mutable materialized view as an append-only incremental source. Select the latest
capture timestamp when querying history, and deduplicate replayed `eventId`
values; neither ingestion nor twin mapping is claimed to be exactly once.

Event silence never changes occupancy or establishes camera availability. The
OneLake target latency is a batching target, not an end-to-end refresh guarantee.

## Publish And Initialize

1. After `apply`, open `tiger_ingest` and its `CameraEvents` Custom App source.
   Privately configure its Event Hub-compatible connection string and hub name
   using the [detect relay settings](../../apps/detect/README.md#fabric-publishing-and-edge-migration).
   The bootstrap does not retrieve or write SAS credentials. Signed-in deployment
   authentication does not replace Custom App source publishing credentials.
2. Verify the Eventstream destination is `ProcessEventsRaw` in `tiger_events_db`
   and preserves the top-level JSON fields. The versioned definition uses processed
   ingestion. The named KQL JSON mapping remains available for direct ingestion;
   it does not configure Eventstream field mapping by itself.
3. Send events with the existing relay. For example, relay the completed jeep
   trial file after setting the private connection settings:

   ```bash
   uv run --directory apps/detect --extra fabric python -m tiger_perception.fabric \
     --input ../../data/cell-a/jeep-events.jsonl --live-fabric \
     --output ../../data/fabric-audit.jsonl
   ```

4. Run the [sample queries](../../apps/fabric/kql/03_sample_queries.kql)
   individually. Verify raw ingestion, confirmed booleans, reference joins, both
   presence types, and latest state ordered by capture time.
5. Wait until `ConfirmedPresenceEvents` is readable as a Delta table through the
   `tiger_reference` shortcut. Empty Eventhouse tables may not yet have a readable
   OneLake representation. If creation of a mapping fails because its source is
   not ready, retain the checkpoint, publish valid events, verify readiness, and
   rerun `apply`. Do not inject synthetic occupancy merely to initialize a table.
6. In Fabric, run `tiger_reference_flow` and wait for completion. Then run
   `tiger_relationships_flow` and wait. Verify one plant, two cells, four positions,
   and the two relationship types. Finally run `tiger_timeseries_flow` and inspect
   event timestamps and state. Configure recurring execution only after these
   one-time checks succeed.

Dashboards remain the PR's design blueprints, not native dashboard import
packages. Follow the [dashboard configuration guide](../../apps/fabric/README.md#configure-twin-and-dashboard-views).

## Optional Job API

`run` and `schedule` are guarded adapters to Fabric's generic job scheduler, not
verified Digital twin builder execution support. There is no assumed job type;
do not guess `Execute` or another value. Only after a supported job type is
confirmed for this item and tenant:

```bash
uv run infra/fabric/deploy.py run --workspace "<workspace-id>" \
  --job-type "<confirmed-job-type>" --phase reference
uv run infra/fabric/deploy.py run --workspace "<workspace-id>" \
  --job-type "<confirmed-job-type>" --phase events
uv run infra/fabric/deploy.py schedule --workspace "<workspace-id>" \
  --job-type "<confirmed-job-type>" --interval 15 --until "<future-UTC-timestamp>"
```

The reference phase runs reference mapping before contextualization. The events
phase requires that initialization checkpoint. Jobs are successful only with
`Completed`, not `Deduped`. Recorded active jobs are polled on retry.

Schedules require successful API-managed initialization and events runs, an
explicit future expiration, and a 15-720 minute interval. Only time-series mapping
is scheduled. Portal runs are not inferred or recorded by the script. Manage and
disable schedules in Fabric; do not overlap portal, manual API, and scheduled
runs. After an interrupted schedule creation, inspect Fabric for an existing
schedule before retrying to avoid a duplicate.

## State And Recovery

Default checkpoints live under ignored `data/fabric/<workspace-id>.json` and
contain IDs, artifact fingerprints, and completion status, not credentials.
Keep this file across retries. `--state` selects another local path; keep it out
of source control. Run only one deployment process for a workspace at a time.

Successful actions are checkpointed. Repeating `apply` with the same state and
artifacts performs inventory checks and skips completed work. Colliding names,
missing owned items, another workspace, or a changed fingerprint stop deployment.
There is no adoption, implicit update, rollback, or deletion command. Do not use
this against manually configured production items.

If creation times out or the connection fails before an item ID is recorded, the
service may still finish. Inspect Fabric before retrying; a name collision then
stops automatic duplicate creation. Diagnose partial resources or remove the
failed item manually before resuming. Do not discard state to bypass a collision.

For a new model version, manually clean up the previous deployment and archive
its state, or use a separate prefix with a separate `--state` file. Remove twin
items before their backing lakehouse; associated flows are deleted with the twin.
Changing public twin definitions is a replacement operation and is intentionally
not implemented as an automatic update.

## Verification And API References

Successful Fabric API access does not prove connectivity to the KQL endpoint.
If configuration stops with a secure-connection error, check HTTPS port 443 access
from the environment running the script to the `queryServiceUri` returned by
Fabric, including DNS, VPN/firewall, proxy and certificate configuration. Do not
disable TLS verification. Retain the checkpoint: a successful database creation is
recorded before KQL policy configuration, so `apply` can resume after connectivity
is restored. Failed policy actions are not marked complete.

```bash
uv run --project apps/detect --extra fabric --with azure-storage-file-datalake --with httpx \
  python -m pytest infra/fabric/tests apps/detect/tests/test_fabric.py apps/detect/tests/test_fabric_contracts.py -q
uv run --project apps/detect ruff check infra/fabric
```

Tests cover artifact conversion, seed alignment, multiline KQL preservation,
encoding, trusted endpoints, throttling, asynchronous completion, name collisions,
state binding, and mocked apply/resume. They do not execute KQL or validate live
Eventstream, OneLake, or Digital twin builder behavior.

* [KQL database definitions](https://learn.microsoft.com/rest/api/fabric/articles/item-management/definitions/kql-database-definition)
* [Eventstream definitions](https://learn.microsoft.com/rest/api/fabric/articles/item-management/definitions/eventstream-definition)
* [Lakehouse CSV loading](https://learn.microsoft.com/rest/api/fabric/lakehouse/tables/load-table)
* [OneLake shortcuts](https://learn.microsoft.com/rest/api/fabric/core/onelake-shortcuts/create-shortcut)
* [Digital twin builder definitions](https://learn.microsoft.com/rest/api/fabric/articles/item-management/definitions/digital-twin-builder-definition)
* [Digital twin builder flow definitions](https://learn.microsoft.com/rest/api/fabric/articles/item-management/definitions/digital-twin-builder-flow-definition)
* [Digital twin builder creation and identity support](https://learn.microsoft.com/rest/api/fabric/digitaltwinbuilder/items/create-digital-twin-builder)
* [Generic job execution](https://learn.microsoft.com/rest/api/fabric/core/job-scheduler/run-on-demand-item-job)

Preview documentation currently differs between mapping enum tables and examples.
The renderer follows the published example casing and base entity type `2`; live
acceptance of these definitions remains a required validation step.
