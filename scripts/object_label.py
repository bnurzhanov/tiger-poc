"""Identify and draw approximate object labels on a camera frame with Foundry Local.

Usage:
    python scripts/object_label.py --image relocated-camera-frame.jpg \
        --output relocated-camera-labeled.jpg
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

import cv2

from vision_check import DEFAULT_MODEL_ALIAS, analyze_image_foundry

logger = logging.getLogger("object_label")

PROMPT = """Identify the distinct visible objects in this image.
Return ONLY valid JSON with this exact shape:
{"objects":[{"label":"car","confidence":0.9,"box":[0.1,0.2,0.4,0.8]}]}
Use at most 20 objects. The box is [left, top, right, bottom], normalized from 0.0 to 1.0.
Use short generic labels such as car, person, tree, building, or road sign.
Do not include reflections, glare, shadows, or image artifacts as objects.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Input image to label")
    parser.add_argument("--output", required=True, help="Annotated output image")
    parser.add_argument("--model", default=DEFAULT_MODEL_ALIAS["foundry"])
    return parser.parse_args()


def extract_objects(response: str) -> list[dict[str, object]]:
    """Parse and validate the model's JSON object predictions."""
    match = re.search(r"\{.*\}", response, re.DOTALL)
    if match is None:
        raise ValueError("model response did not contain a JSON object")

    payload = json.loads(match.group(0))
    objects = payload.get("objects")
    if not isinstance(objects, list):
        raise ValueError("model JSON did not contain an objects list")

    valid: list[dict[str, object]] = []
    for item in objects[:20]:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        confidence = item.get("confidence")
        box = item.get("box")
        if (
            isinstance(label, str)
            and label
            and isinstance(confidence, (int, float))
            and isinstance(box, list)
            and len(box) == 4
            and all(isinstance(value, (int, float)) for value in box)
        ):
            coordinates = [float(value) for value in box]
            if (
                0 <= coordinates[0] < coordinates[2] <= 1
                and 0 <= coordinates[1] < coordinates[3] <= 1
            ):
                valid.append(
                    {
                        "label": label,
                        "confidence": max(0.0, min(1.0, float(confidence))),
                        "box": coordinates,
                    }
                )
    return valid


def draw_labels(image, objects: list[dict[str, object]]):
    """Draw validated normalized boxes and labels onto a copy of the image."""
    labeled = image.copy()
    height, width = labeled.shape[:2]
    for item in objects:
        left, top, right, bottom = item["box"]  # type: ignore[misc]
        x1, y1 = int(left * width), int(top * height)
        x2, y2 = int(right * width), int(bottom * height)
        label = f"{item['label']} {item['confidence']:.2f}"
        cv2.rectangle(labeled, (x1, y1), (x2, y2), (0, 220, 0), 3)
        (text_width, text_height), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2
        )
        label_top = max(y1, text_height + baseline)
        cv2.rectangle(
            labeled,
            (x1, label_top - text_height - baseline),
            (x1 + text_width, label_top),
            (0, 220, 0),
            cv2.FILLED,
        )
        cv2.putText(
            labeled,
            label,
            (x1, label_top - baseline),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )
    return labeled


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    image_path = Path(args.image)
    image = cv2.imread(str(image_path))
    if image is None:
        logger.error("Could not read image: %s", image_path)
        return 2

    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        logger.error("Could not encode image: %s", image_path)
        return 1

    response = analyze_image_foundry(args.model, PROMPT, encoded.tobytes(), "jpeg")
    try:
        objects = extract_objects(response)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("Invalid object response: %s", exc)
        return 1

    output = draw_labels(image, objects)
    if not cv2.imwrite(args.output, output):
        logger.error("Could not write image: %s", args.output)
        return 1
    logger.info("Labeled %d objects; wrote %s", len(objects), args.output)
    print(json.dumps({"objects": objects}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())