---
title: RTSP YOLO Detection Example
description: Minimal instructions for running YOLO detection against an RTSP camera
---

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

Press `Ctrl+C` to stop. Detection records are written to
`apps/detect/detections.jsonl`.
