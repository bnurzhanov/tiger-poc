"""Serve a localhost-by-default recording view from local workload artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import Workload, load_workload

PAGE = Path(__file__).parent / "viewer.html"


def cell_status(workload: Workload, *, now: datetime | None = None) -> dict:
    """Never treat an old status file or preview as current camera evidence."""
    now = now or datetime.now(UTC)
    status = {
        "name": workload.metadata.name, "sourceId": workload.spec.source.id,
        "subjectId": workload.spec.source.subjectId, "plantName": workload.metadata.plantName,
        "observationType": workload.spec.perception.observationType,
        "labels": workload.spec.perception.labels, "region": workload.spec.region.bounds,
        "availability": "unavailable", "lastConfirmed": None, "reason": "Workload not running",
        "latestEvent": None, "metrics": {}, "capturedAt": None,
    }
    try:
        saved = json.loads(Path(workload.spec.destination.statusPath).read_text())
        if saved["sourceId"] != status["sourceId"] or saved["subjectId"] != status["subjectId"]:
            raise ValueError("status identity mismatch")
        written = datetime.fromisoformat(saved["writtenAt"])
        captured = datetime.fromisoformat(saved["capturedAt"]) if saved.get("capturedAt") else None
        status.update(saved)
        age = (now - captured).total_seconds() if captured else None
        status["evidenceAgeSeconds"] = age
        if (not 0 <= (now - written).total_seconds() < workload.spec.presence.staleSeconds
                or age is None or not 0 <= age < workload.spec.presence.staleSeconds):
            status["availability"] = "unavailable"
            status["reason"] = "Stale or missing evidence"
    except (OSError, ValueError, KeyError, TypeError):
        status["availability"] = "unavailable"
        status["reason"] = "Workload status unavailable"
    return status


def create_server(workloads: list[Workload], port: int, *, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """Expose only the viewer, redacted status, and configured preview images."""
    if host not in {"127.0.0.1", "0.0.0.0"}:
        raise ValueError("Select loopback or the explicit container bind address")
    if not workloads or len(workloads) > 2:
        raise ValueError("Select one or two manifests")
    for values in (
        [item.spec.source.id for item in workloads],
        [item.spec.source.subjectId for item in workloads],
        [item.spec.source.uriFrom for item in workloads],
    ):
        if len(values) != len(set(values)):
            raise ValueError("Workloads must have independent camera and position identities")
    outputs = [path for item in workloads for path in (
        item.spec.destination.path, item.spec.destination.statusPath,
        str(Path(item.spec.destination.statusPath).with_suffix(".jpg"))) ]
    if len(outputs) != len(set(outputs)):
        raise ValueError("Workloads must have separate outputs")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            route = self.path.split("?", 1)[0]
            if route == "/":
                content = PAGE.read_bytes()
                content_type = "text/html; charset=utf-8"
            elif route == "/api/cells":
                content = json.dumps([cell_status(item) for item in workloads]).encode()
                content_type = "application/json"
            elif route in {f"/preview/{index}.jpg" for index in range(len(workloads))}:
                index = int(route.split("/")[2].split(".")[0])
                path = Path(workloads[index].spec.destination.statusPath).with_suffix(".jpg")
                try:
                    content = path.read_bytes()
                except OSError:
                    self.send_error(404)
                    return
                content_type = "image/jpeg"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


def create_parser() -> argparse.ArgumentParser:
    """Create viewer arguments; no secret environment file is required."""
    parser = argparse.ArgumentParser(description="Read-only local camera workload view")
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1",
                        help="Use 0.0.0.0 only inside a container with a localhost-published port.")
    return parser


def main() -> int:
    """Run the loopback viewer until interrupted."""
    args = create_parser().parse_args()
    try:
        workloads = [load_workload(path) for path in args.manifest]
        with create_server(workloads, args.port, host=args.host) as server:
            print(f"Recording view: http://127.0.0.1:{server.server_port}", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError):
        print("Cannot start viewer. Check manifests, unique outputs, and available port.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())