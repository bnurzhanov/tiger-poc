"""Manifest-driven edge perception pipeline runner."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from .contracts import ProcessEvent, RawDetection
from .presence import PresenceRuleConfig, RegionConfig, RegionPresenceRule
from .sinks import FabricEventstreamSink, LocalJsonlSink

logger = logging.getLogger(__name__)


def load_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """Load and parse a YAML perception manifest."""
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def create_rule_from_manifest(manifest: dict[str, Any]) -> RegionPresenceRule:
    """Instantiate a RegionPresenceRule from a parsed manifest."""
    spec = manifest.get("spec", {})
    sources = spec.get("sources", [{}])[0]
    perception = spec.get("perception", {})
    region_data = spec.get("region", {"x_min": 0.2, "y_min": 0.2, "x_max": 0.8, "y_max": 0.8})
    destination = spec.get("destination", {})

    region = RegionConfig(
        x_min=float(region_data.get("x_min", 0.0)),
        y_min=float(region_data.get("y_min", 0.0)),
        x_max=float(region_data.get("x_max", 1.0)),
        y_max=float(region_data.get("y_max", 1.0)),
    )

    config = PresenceRuleConfig(
        source_id=sources.get("id", "default-camera"),
        subject_id=sources.get("subjectId", "default-subject"),
        region=region,
        target_class=perception.get("targetClass", "pallet"),
        confidence_threshold=float(perception.get("confidenceThreshold", 0.5)),
        occupied_confirmation_frames=int(perception.get("occupiedConfirmationFrames", 3)),
        empty_confirmation_frames=int(perception.get("emptyConfirmationFrames", 5)),
        provider=perception.get("provider", "local-yolo"),
        model=perception.get("model", "yolo26n-pallet"),
        plant_name=spec.get("plantName", "Demo Plant 01"),
        plant_id=spec.get("plantId", "demo-plant-01"),
    )
    return RegionPresenceRule(config)


def create_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""
    parser = argparse.ArgumentParser(description="Run edge perception workload from manifest.")
    parser.add_argument("--manifest", type=Path, required=True, help="Path to PerceptionWorkload manifest YAML.")
    parser.add_argument("--output", type=Path, default=Path("detections.jsonl"), help="Output JSONL path.")
    parser.add_argument("--fabric", action="store_true", help="Enable Fabric Eventstream publishing.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run Fabric sink in dry-run mode.")
    return parser


def main() -> int:
    """Main CLI execution."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = create_parser().parse_args()

    manifest = load_manifest(args.manifest)
    rule = create_rule_from_manifest(manifest)
    logger.info("Loaded workload: %s for subject: %s", manifest.get("metadata", {}).get("name"), rule.config.subject_id)

    local_sink = LocalJsonlSink(path=args.output)
    fabric_sink = FabricEventstreamSink(dry_run=args.dry_run, fallback_jsonl_path=args.output) if args.fabric else None

    logger.info("Workload pipeline initialized. Awaiting camera/stream frames...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
