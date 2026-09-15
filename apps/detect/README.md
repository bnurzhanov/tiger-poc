---
title: RTSP YOLO Detection Example
description: Minimal instructions for running YOLO detection against an RTSP camera
---

## Perception layer

This app is currently the first producer of the shared perception contract. The RTSP
YOLO detector emits ProcessEvent records, but the model is intentionally designed to
accept other sensor telemetry as well: video detections, machine-state signals,
thermal readings, and future observation sources can all publish into the same
contract.

The local JSONL sink in `tiger_perception` validates every ProcessEvent before it is
written, redacts secret fields, rejects invalid payloads, and supports deterministic
replay of persisted observations.

## Run

From the repository root, install the dependencies:

```bash
uv sync --project apps/detect
```

Run detection with your camera credentials and stream path:

```bash
RTSP_URL='rtsp://user:password@192.168.2.102:554/cam/realmonitor?channel=1&subtype=0' \
  uv run --project apps/detect apps/detect/rtsp_yolo.py
```

Press `Ctrl+C` to stop. ProcessEvent records are written to
`apps/detect/detections.jsonl` using the sensor-agnostic perception contract.
