---
title: Local Two-Cell Perception
description: Run independent manifest-driven camera workloads, inspect confirmed presence, and rehearse milestone 1.
---

## Scope

Each local process reads one RTSP camera, runs Ultralytics detection, confirms one
configured region's occupancy, and writes its own schema-validated `ProcessEvent`
JSONL output. No cloud service is required. A localhost-by-default browser view reads both
processes' status files and annotated previews without accessing camera credentials.

The bundled `yolo26n.pt` supports **chair**, not pallet. The prepared
[Cell A](manifests/cell-a.yaml) and [Cell B](manifests/cell-b.yaml) configurations
are household-object trials emitting `ObjectPresent`. They do not satisfy the
physical pallet-model or recording criteria. The [root manifest](../../manifest.yaml)
and [Cell B pallet manifest](manifests/cell-b-pallet.yaml) are the paired pallet
templates and require trusted local pallet weights at `models/pallet.pt`; no such
model is bundled. Use these instead of the household manifests after supplying and
validating the weights. See the
[validation record](../../docs/milestone-1-validation.md) for remaining gates.

## Prepare

Use Linux (including WSL), Python 3.14 or newer, `uv`, and network access to the
cameras' actual RTSP stream endpoints. Start with CPU inference and two threads per
process; measure both workloads before increasing image size or sampling rate.
Use only trusted model weight files. Review the Ultralytics and weight licenses
before distributing this accelerator.

From the repository root:

```bash
uv sync --project apps/detect
```

Privately set `CAMERA_A_RTSP_URL` and `CAMERA_B_RTSP_URL` in `apps/.env`.
That filename is gitignored. Do not put endpoints or credentials in the manifests,
command line, screenshots, or event extensions. Existing environment variables take
precedence over the environment file. Percent-encode reserved characters in URL
credentials. Configure the full camera stream path, not only the camera's address.

For the chair trial, choose two differently arranged floor areas. Keep the entire
chair visible with stable lighting. An object matches when its bounding-box center
is inside the yellow rectangle; the green boxes are qualifying detections. Edit
each manifest's `region.bounds` to match its view before recording. Keep other
chairs outside the region. Toy vehicles are not validated substitutes for real cars.

## Launch

Preflight camera A's configuration and model labels without opening the camera:

```bash
uv run --project apps/detect apps/detect/rtsp_yolo.py \
  --manifest apps/detect/manifests/cell-a.yaml --env-file apps/.env --check
```

Run these commands in separate terminals for concurrent operation:

```bash
uv run --project apps/detect apps/detect/rtsp_yolo.py \
  --manifest apps/detect/manifests/cell-a.yaml --env-file apps/.env
```

```bash
uv run --project apps/detect apps/detect/rtsp_yolo.py \
  --manifest apps/detect/manifests/cell-b.yaml --env-file apps/.env
```

In another terminal, start the view:

```bash
uv run --directory apps/detect python -m tiger_perception.viewer \
  --manifest manifests/cell-a.yaml --manifest manifests/cell-b.yaml --port 8765
```

Open <http://127.0.0.1:8765>. Use another port if 8765 is occupied. A narrow browser
window stacks the cells; use a wide window for side-by-side recording. The viewer
binds only to loopback and exposes no directory listing or camera configuration.
This implementation supports both workloads on one Linux dev box; distributed
viewer aggregation is not implemented or required for this placement.

Press `Ctrl+C` in each workload terminal for shutdown. Events are appended to
`data/cell-a/events.jsonl` and `data/cell-b/events.jsonl`. Status and previews are
local diagnostic artifacts in the same directories. These paths are gitignored;
review frames for private surroundings before sharing them. Archive outputs
between rehearsals. Restarting initializes unknown state and emits a new initial
event with a new ID; restart persistence is not provided.

The original `rtsp_yolo.py` arguments remain supported for per-frame detection
diagnostics. They are not the milestone presence pipeline. Use `--manifest` for
the new runner; use `python -m tiger_perception.viewer` from the detector directory
for the viewer, not its Python file path.

## Docker Compose

[Compose](../docker-compose.yml) runs the Cell A Jeep trial (`car` detection),
its browser viewer, and an optional live Fabric publisher. It does not provision
Fabric items. Create the Eventstream Custom App source before enabling publishing.
Docker Engine with Compose must be available from WSL. The build uses the approved
Python package feed, disables automatic interpreter downloads, and uses Python
from the base image. Building also requires access to Docker Hub, GHCR, and Debian
package repositories under your organization's policies.

Privately configure `CAMERA_A_RTSP_URL` in `apps/.env`. Use the camera's reachable
LAN address; `localhost` inside the container refers to the container itself.
From the repository root, start the local camera and viewer:

```bash
mkdir -p data
docker compose --env-file apps/.env -f apps/docker-compose.yml up --build -d
```

Open <http://127.0.0.1:8765>. Set `VIEWER_PORT` in the environment file if that port
is occupied. The image runs as UID/GID 1000; the host data directory and secret
file must be accessible to that identity. Do not make credentials world-readable.
The viewer binds to all container interfaces but publishes its host port only on
loopback. It has no authentication and must not be exposed to the LAN or internet.
The detector alone receives camera credentials. The viewer and publisher mount
detector output read-only.

To enable live Fabric publishing, put the Custom App source's complete connection
string into `apps/secrets/fabric-connection-string`. That directory is gitignored.
For example, enter it privately without placing the value in shell history:

```bash
mkdir -p apps/secrets
chmod 700 apps/secrets
read -rsp 'Fabric connection string: ' fabric_connection_string
printf '\n'
(umask 077; printf '%s' "$fabric_connection_string" > apps/secrets/fabric-connection-string)
unset fabric_connection_string

docker compose --env-file apps/.env -f apps/docker-compose.yml --profile fabric up --build -d
```

The publisher reads the mounted secret file, waits for the detector's event file,
then follows complete new records. Its first run also sends any existing backlog.
Only the publisher receives this secret. Compose secret files are local files,
not an encrypted secret store. Never commit them or paste their contents into logs.

```bash
docker compose --env-file apps/.env -f apps/docker-compose.yml --profile fabric logs -f detect publisher
docker compose --env-file apps/.env -f apps/docker-compose.yml --profile fabric down
```

The publisher's delivery checkpoint lives in the `publisher-state` named volume
at `/var/lib/tiger-publisher/delivery.json`, separate from Fabric provisioning
checkpoints. Ordinary `down` retains it; do not use `down -v` during normal
restarts. The detector's event, status, and preview files stay in the host `data`
directory. Keep event files append-only. Do not rotate, truncate, or replace a
followed file without stopping the publisher and reconciling its delivery state.
This version does not automatically compact acknowledged files; monitor disk space.
Changing the camera manifest also requires matching viewer and publisher input
paths in Compose. Do not run a host detector against the same outputs concurrently.

## Configuration Contract

File paths resolve relative to the manifest, not the working directory. Unknown
keys, missing identities, invalid geometry, unsupported providers, invalid timing,
and unsupported model labels fail startup. One source and one position are allowed
per manifest. Output file locks prevent two local processes sharing a destination.

| Setting | Meaning |
| --- | --- |
| `metadata.name`, `plantName`, `plantId` | Deployment and stable plant attribution |
| `spec.source.id`, `subjectId` | Stable camera and monitored-position identity |
| `source.type`, `uriFrom` | `rtsp` or development `replay`; environment reference only |
| `perception.model`, `provider`, `labels` | Trusted local detection weights, `ultralytics`, supported class names |
| `perception.observationType` | `PalletPresent` requires exactly `[pallet]`; household trials use `ObjectPresent` |
| `perception.sampleEveryFrames` | Sampling stride before the bounded capture queue |
| `perception.device`, `threads`, `imageSize` | Local runtime settings; defaults `cpu`, 2, 640 |
| `region.coordinates`, `matching` | `normalized-xyxy`, inclusive `box-center` |
| `region.bounds` | `[left, top, right, bottom]`, each in `[0, 1]`, positive area |
| `presence.confidence` | Minimum qualifying detector score, default trial value 0.5 |
| `presence.occupiedSeconds`, `emptySeconds` | Continuous evidence windows, trial defaults 2 and 3 seconds |
| `presence.staleSeconds` | Maximum evidence age and observation gap, trial default 2 seconds |
| `capture.timeoutMilliseconds` | Native camera open/read timeout, default 1500; hard process watchdog also applies |
| `capture.minBrightness`, `maxBrightness`, `minContrast` | Image rejection thresholds: defaults 5, 250, 2 on 8-bit grayscale |
| `destination.connector`, `path`, `statusPath` | `local-jsonl`, separate event and live-view artifacts |

The image-quality checks detect black, white, or textureless frames; they cannot
establish adequate focus, visibility, or absence of occlusion. Validate thresholds
against both real views. A plausible but obstructed image can still fool the model.

### State And Evidence

Start unknown. Confirm occupied or empty only after at least two distinct usable
frames span the appropriate window. Flicker resets the candidate timer. Initial
confirmation emits one event; unchanged observations emit none. Each source and
subject has its own rule instance.

Failed reads, failed inference, invalid geometry, non-increasing sequences,
out-of-order timestamps, unusable images, or stale evidence reset pending
confirmation and mark evidence unavailable. Recovery requires a fresh complete
window. Recovering to the same last confirmed value produces no event. Explicit
capture reconnect epochs allow sequence restart without accepting ordinary
out-of-order evidence.

`lastConfirmed` is historical and separate from `availability` (`unknown`,
`confirming`, `current`, `unavailable`). The viewer marks old status files and
previews stale even if the producer has stopped. Events are transitions, not health
heartbeats; silence is neither evidence of empty space nor proof of camera health.

### Timestamps And Confidence

`Frame.captured_at` is the local UTC start of the decode/read operation, not a
verified camera hardware timestamp. `RawInference.produced_at` is inference
completion. `ProcessEvent.publishedAt` is assigned before publication. The event's
`capturedAt` refers to the final confirming frame; `confirmationStartedAt` and
`confirmationFrames` retain window evidence.

Normalized raw boxes are `[0, 1]` xyxy. `RawInference.succeeded` explicitly
distinguishes successful zero detections from inference failure. Occupied confidence
is the minimum of the best qualifying scores observed across the confirmation
window. Empty confidence is **0.0, not estimated**, never `1 - detectorConfidence`;
the event's `confidenceMeaning` states this. These are rule semantics, not calibrated
probabilities of physical occupancy.

Events preserve the actual Ultralytics version and weight filename plus SHA-256,
stable source/subject IDs, and plant metadata. Mapping preserves the observation's
UUID for retries. The sink validates the checked-in JSON Schema and presence boolean
semantics, flushes and fsyncs, retries write failures at most three times, and fails
the workload visibly on exhaustion. Duplicate IDs are suppressed within a process.
This is not exactly-once delivery across crashes or restarts; an ambiguous write
failure can require deduplication by event ID during analysis.

### Capture And Performance

A dedicated capture process continuously drains frames into a one-frame queue,
dropping old queued frames when inference falls behind. Sampling-stride skips are
intentional and are not queue drops. The view reports queue drops, processed FPS,
latest inference duration, evidence age, and publication failures. Open/read hangs
trigger a hard worker restart. RTSP reconnects invalidate pending confirmation;
end-of-file for replay remains unavailable rather than looping into a new scene.

Host receive timestamps and a bounded application queue cannot detect every stale
buffer inside a camera or decoder. Verify physical movement against the view and
measure end-to-end delay during rehearsal. Reduce camera stream resolution or model
image size if two concurrent workloads cannot maintain fresh evidence. Do not
increase `staleSeconds` merely to conceal lag.

## Rehearsal And Checks

1. Confirm both feeds, independent identities, and yellow regions match the manifests.
2. Keep both regions empty through the initial three-second confirmation windows.
3. Put the chair in A and hold for two seconds plus processing delay; B stays empty.
4. Put a second chair in B, then remove A's chair; verify isolated transitions.
5. Leave both scenes unchanged and verify event counts stop increasing.
6. Briefly move a chair in and out faster than confirmation; verify no flicker event.
7. Disconnect A or cover its lens fully; it must become unavailable, not empty.
8. Restore A with the same occupancy; require reconfirmation with no duplicate event.
9. Repeat with B, then archive events, metrics, configuration, and redacted evidence.

Record hardware, startup/adaptation time, camera placement, light/occlusion limits,
false detections and misses, processed throughput, dropped frames, and observed
confirmation delay. Use the [partner script](../../docs/demo-script.md) only after
the actual pallet criteria are met or an explicit scope change is approved. Label
cuts; two minutes is the video length, not a startup or latency promise.

Run software gates from the repository root:

```bash
uv run --project apps/detect python -m pytest apps/detect/tests -q
uv run --project apps/detect ruff check apps/detect
uv run --project apps/detect python -m compileall -q apps/detect/tiger_perception apps/detect/rtsp_yolo.py
```

Tests include real local-file decoding, deterministic provider doubles, timing,
outages, schema validation, retries, two-output isolation, and stale-view handling.
For manual video replay, set `source.type: replay` and resolve `uriFrom` to a private
local clip path. Replay is paced at the video FPS and uses the same real inference
adapter. Neither replay nor fixtures replace physical camera validation.

## Fabric Publishing And Edge Migration

This project owns the supported Python implementation and the `tiger_perception`
package. Use its canonical contracts, time-based presence policy and manifest
runner. The existing manifest runner and local JSONL destination are unchanged.

The [Fabric relay](tiger_perception/fabric.py) preserves remote publishing, optional
local audit traces and the six-transition multi-cell demo. It imports the same
`ProcessEvent`, validator and JSONL sink as detection. Cloud SDKs are optional and
loaded only for live publication. Install the optional dependencies from the root:

```bash
uv sync --project apps/detect --extra fabric
```

Run the offline demo; its cell A object and cell B pallet identities match the
shipped manifests. Synthetic empty confidence is 0.0, as in the presence rule.
The scenario spans 28 seconds of event time and is not a latency measurement.

```bash
uv run --directory apps/detect --extra fabric python -m tiger_perception.fabric \
  --demo --dry-run --output ../../data/fabric-demo.jsonl
```

Validate completed camera event files without modifying them:

```bash
uv run --directory apps/detect --extra fabric python -m tiger_perception.fabric \
  --input ../../data/cell-a/events.jsonl ../../data/cell-b/events.jsonl \
  --dry-run --output ../../data/fabric-audit.jsonl
```

Replace `--dry-run` with `--live-fabric` only after configuring a destination
privately in the process 
environment. The relay does not load `apps/.env`.

| Environment variable | Purpose |
| --- | --- |
| `FABRIC_EVENTSTREAM_NAMESPACE` | Event Hubs namespace hostname for `DefaultAzureCredential`, preferred for Azure Event Hubs |
| `FABRIC_EVENTSTREAM_EVENTHUB_NAME` | Required with namespace authentication; optional with an entity-scoped connection string |
| `AZURE_CLIENT_ID` | On an Azure host, selects the attached user-assigned managed identity using the `managedIdentityClientId` deployment output |
| `FABRIC_EVENTSTREAM_CONNECTION_STRING` | Fabric Custom App source connection string, or existing Event Hubs sender credentials |
| `FABRIC_EVENTSTREAM_CONNECTION_STRING_FILE` | UTF-8 file containing the connection string, used when namespace and direct connection string are unset |
| `MOCK_FABRIC` | `1`, `true`, or `yes` forces offline mode even with live arguments |

Namespace authentication takes precedence over connection strings.
Grant the publishing identity **Azure Event Hubs Data Sender** on the target hub.
The [infrastructure template](../../infra/digital-twin-poc/README.md) grants this
role to its provisioned user-assigned identity. Attach that identity to your Azure
compute host using `managedIdentityResourceId`, and set `AZURE_CLIENT_ID` to
`managedIdentityClientId` in the relay's process environment. Set the namespace
hostname and hub name from `eventHubNamespaceHostname` and `eventHubName` too.
The template does not deploy a compute host or attach the identity to one.

`DefaultAzureCredential` already reads `AZURE_CLIENT_ID` for its managed-identity
candidate; this setting does not force the entire credential chain to use it.
For local WSL or laptop execution, sign in with an available developer credential
and grant that developer identity the sender role separately. Setting the managed
identity's client ID does not make it available locally. The relay does not assign
roles or deploy resources. No configured destination in live mode is an error,
not a dry run. See the
[Azure Identity reference](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential).

Without `--follow`, input mode reads completed JSONL files once. For continuous
publication from a running detector, configure the destination privately and run:

```bash
uv run --directory apps/detect --extra fabric python -m tiger_perception.fabric \
  --input ../../data/cell-a/jeep-events.jsonl --follow \
  --checkpoint ../../data/fabric-delivery/jeep.json --live-fabric
```

Follow mode starts from the beginning without a checkpoint, waits for input files
to appear, and reads only newline-terminated records (up to 1 MiB each). It uses
an exclusive Linux file lock and atomically saves each byte offset after the SDK
acknowledges publication. Multiple inputs are polled fairly; a partial line in one
does not block another. `--poll-interval` defaults to 0.25 seconds. Use one durable
checkpoint per input set and destination; dry-run checkpoints cannot be reused
for live delivery. Do not change a destination while reusing its delivery state.

Invalid records, replaced/truncated inputs, and publication failures stop the
relay without skipping the failed event. SDK retries remain enabled; Compose
restarts the publisher after failure and resumes its acknowledged offsets. A crash
between remote acceptance and saving the checkpoint can resend an event: delivery
is at-least-once, not exactly-once. Deduplicate by `eventId` downstream. Checkpoint
locking only prevents duplicate publishers using that same checkpoint; do not run
multiple publishers with different checkpoints against the same destination/input.

Original IDs, timestamps and evidence are retained with canonical secret redaction.
Local audit traces are not remote delivery acknowledgments and are unnecessary
for the normal Compose publisher. Audit output and checkpoint paths must differ
from every input. `--iterations` repeats only the demo; `--interval` paces one-shot
publication. A presence event represents initialization or a confirmed transition,
not every frame. Silence still does not mean empty occupancy or camera health.

Run publisher and artifact checks with the optional dependencies installed:

```bash
uv run --project apps/detect --extra fabric pytest apps/detect/tests/test_fabric.py apps/detect/tests/test_fabric_contracts.py -q
```

Configure ingestion and reference identities using the
[Fabric setup](../fabric/README.md). SDK reference:
[Event Hubs Python client](https://learn.microsoft.com/python/api/overview/azure/eventhub-readme).

## Troubleshooting

* Missing camera reference: set the named variable privately in the environment file
* Unsupported labels: use a supported household label or provide pallet-capable weights
* No frames: check the full stream path, RTSP credentials, camera session limits, TCP routing, and stream codec
* Unavailable after inference: inspect frame age, image quality, and concurrent compute pressure
* Output locked: stop the other owner or choose separate manifest paths
* Publication failure: check disk space and permissions; the workload stops instead of silently losing a transition
