# Microsoft Fabric Digital Twin & Real-Time Intelligence

This component configures Microsoft Fabric to ingest edge `ProcessEvent` records from factory cells, maintain a live digital twin state, and display near real-time operational status via Fabric Real-Time Dashboard or Power BI.

## Architecture & Data Flow

```text
Edge Cameras / Replay Simulator
           |
           | (ProcessEvents JSON)
           v
Fabric Eventstream (Custom App source / Event Hubs)
           |
           +---> Fabric Eventhouse (KQL Database)
           |         |
           |         +---> Table: ProcessEventsRaw
           |         +---> Materialized View: CurrentPalletOccupancy
           |         +---> Reference Tables: Plants, Cells, PalletPositions
           |
           +---> Digital Twin Builder (Preview)
                     |
                     +---> Entities: Plant -> Cell -> PalletPosition
                     +---> Telemetry Binding: PalletPresent state
```

## Step-by-Step Setup in Microsoft Fabric

### Step 1: Create an Eventstream
1. In your Fabric Workspace, create a new **Eventstream**.
2. Add a **Custom App** source (or Azure Event Hubs source if deployed via [infra/digital-twin-poc/main.bicep](../../infra/digital-twin-poc/main.bicep)).
3. Copy the **Connection String** or **Event Hub Ingestion Endpoint**.
4. Set destination to your **KQL Database** targeting table `ProcessEventsRaw`.

### Step 2: Execute KQL Setup Scripts
Open your Fabric KQL Queryset or Eventhouse database and run the scripts in order:
1. `kql/01_create_tables.kql` - Creates tables and ingestion mappings.
2. `kql/02_update_policy.kql` - Sets up continuous state aggregation and materialized views.
3. `kql/03_sample_queries.kql` - Test sample queries.

### Step 3: Configure Digital Twin Builder (Preview)
1. In Fabric Real-Time Intelligence, open **Digital Twin Builder**.
2. Import the ontology definition from `digital_twin/ontology_definition.json`.
3. Import the initial graph instances from `digital_twin/twin_instances.json`.
4. Bind incoming telemetry from `ProcessEventsRaw` to `PalletPosition.isOccupied`.

### Step 4: Setup Real-Time Dashboard / Power BI
- **Fabric Real-Time Dashboard**: Create a new Real-Time Dashboard in Fabric and import `dashboards/fabric_realtime_dashboard.json` with 5-second auto-refresh.
- **Power BI Desktop**: Open Power BI, choose **DirectQuery** to KQL Database using `dashboards/powerbi_directquery_kql.m`, and enable **Automatic Page Refresh** (5 seconds).
