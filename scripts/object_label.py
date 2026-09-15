"""Capture or load a frame, label objects, and render its visible edges.

Usage:
    python scripts/object_label.py --host 10.0.0.12 \
        --output camera-labeled.jpg --edges-output camera-edges.jpg
    python scripts/object_label.py --backend mlx --host 10.0.0.12 \
        --output camera-labeled.jpg --edges-output camera-edges.jpg
    python scripts/object_label.py --image camera-frame.jpg \
        --output camera-labeled.jpg --edges-output camera-edges.jpg
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

import cv2
import numpy as np

try:
    from vision_check import (
        DEFAULT_MODEL_ALIAS,
        analyze_image_foundry,
        analyze_image_mlx,
        capture_frame,
    )
except ModuleNotFoundError as exc:
    if exc.name != "vision_check":
        raise
    from scripts.vision_check import (
        DEFAULT_MODEL_ALIAS,
        analyze_image_foundry,
        analyze_image_mlx,
        capture_frame,
    )

logger = logging.getLogger("object_label")

PROMPT = """Identify the distinct visible objects in this image by examining their actual
pixel locations. Return ONLY valid JSON with a single key "objects", a list of entries each
having "label" (a short generic noun such as car, person, tree, building, or road sign),
"confidence" (a number from 0.0 to 1.0), and "box" (a 4-number list [left, top, right, bottom]
normalized from 0.0 to 1.0, measured from the real position of that specific object in this
image).
Report at most 10 objects, only ones you can clearly see, each with a distinct box.
Do not repeat the same box for multiple entries. Do not include reflections, glare, shadows,
or image artifacts as objects.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image", help="Input image to label; capture one camera frame when omitted"
    )
    parser.add_argument("--host", default=None, help="Camera host; defaults to TAPO_HOST")
    parser.add_argument("--quality", choices=("hd", "sd"), default="hd")
    parser.add_argument("--deglare", action="store_true")
    parser.add_argument("--output", default="camera-labeled.jpg")
    parser.add_argument("--edges-output", default="camera-edges.jpg")
    parser.add_argument(
        "--backend",
        choices=("foundry", "mlx"),
        default="foundry",
        help="Inference backend to use for object recognition",
    )
    parser.add_argument("--model", default=None)
    return parser.parse_args()


def _find_balanced_object(text: str) -> str:
    """Return the first top-level ``{...}`` span in ``text``, brace-balanced.

    A naive ``re.search(r"\\{.*\\}")`` greedily spans from the first ``{`` to
    the *last* ``}`` in the whole response, which swallows any trailing prose
    or a second malformed blob the model appended after a valid JSON object.
    Walking braces instead stops at the matching close of the first object.
    """
    start = text.find("{")
    if start == -1:
        raise ValueError("model response did not contain a JSON object")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise ValueError("model response contained an unterminated JSON object")


def _repair_truncated_objects(raw: str) -> dict[str, object]:
    """Best-effort recovery for a JSON object whose trailing content is malformed.

    Small quantized instruct models occasionally break formatting partway
    through a long ``objects`` array (e.g. a missing comma or stray token).
    Rather than discard the whole response, decode as many complete
    ``objects`` array entries as possible up to the failure point.
    """
    array_match = re.search(r'"objects"\s*:\s*\[', raw)
    if array_match is None:
        raise ValueError("model JSON did not contain an objects list")

    decoder = json.JSONDecoder()
    pos = array_match.end()
    items: list[object] = []
    while True:
        # Skip separators/whitespace between array entries.
        while pos < len(raw) and raw[pos] in " \t\r\n,":
            pos += 1
        if pos >= len(raw) or raw[pos] == "]":
            break
        try:
            item, end = decoder.raw_decode(raw, pos)
        except json.JSONDecodeError:
            break
        items.append(item)
        pos = end

    if not items:
        raise ValueError("model JSON did not contain any usable objects")
    return {"objects": items}


def extract_objects(response: str) -> list[dict[str, object]]:
    """Parse and validate the model's JSON object predictions."""
    try:
        raw = _find_balanced_object(response)
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        # Covers both a malformed-but-closed object (e.g. a missing comma)
        # and a truncated/unterminated one (e.g. the model got stuck in a
        # repetition loop and never emitted a closing brace before hitting
        # the token limit). Either way, salvage whatever complete array
        # entries precede the failure instead of discarding the response.
        logger.warning("Model JSON malformed (%s); attempting partial recovery", exc)
        payload = _repair_truncated_objects(response)

    objects = payload.get("objects")
    if not isinstance(objects, list):
        raise ValueError("model JSON did not contain an objects list")

    skipped_shape = 0
    valid: list[dict[str, object]] = []
    for item in objects[:20]:
        if not isinstance(item, dict):
            skipped_shape += 1
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
    if skipped_shape:
        logger.warning(
            "Skipped %d of %d model entries: not in the expected "
            "{label, confidence, box} shape (model likely ignored the schema)",
            skipped_shape,
            len(objects[:20]),
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


def detect_edges(image: np.ndarray) -> np.ndarray:
    """Create a high-contrast edge image without changing the source frame."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    return cv2.Canny(blurred, threshold1=60, threshold2=160)


def load_image(args: argparse.Namespace) -> tuple[np.ndarray, bytes, str]:
    """Load an image from disk or capture one frame from the configured camera."""
    if args.image:
        image_path = Path(args.image)
        if not image_path.is_file():
            raise FileNotFoundError(f"Image not found: {image_path}")
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Could not read image: {image_path}")
        image_bytes = image_path.read_bytes()
        image_format = image_path.suffix.lstrip(".").lower() or "jpeg"
        return image, image_bytes, "jpeg" if image_format == "jpg" else image_format

    image_bytes = capture_frame(args.host, args.quality, None, args.deglare)
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode the captured camera frame")
    return image, image_bytes, "jpeg"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    try:
        image, image_bytes, image_format = load_image(args)
    except (FileNotFoundError, ValueError, SystemExit) as exc:
        logger.error("%s", exc)
        return 2

    model = args.model or DEFAULT_MODEL_ALIAS[args.backend]
    if args.backend == "mlx":
        response = analyze_image_mlx(model, PROMPT, image_bytes)
    else:
        response = analyze_image_foundry(model, PROMPT, image_bytes, image_format)
    try:
        objects = extract_objects(response)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("Invalid object response: %s", exc)
        logger.error("Raw model response:\n%s", response)
        return 1

    output = draw_labels(image, objects)
    if not cv2.imwrite(args.output, output):
        logger.error("Could not write image: %s", args.output)
        return 1
    edges = detect_edges(image)
    if not cv2.imwrite(args.edges_output, edges):
        logger.error("Could not write edge image: %s", args.edges_output)
        return 1
    logger.info(
        "Labeled %d objects; wrote %s and edge view %s",
        len(objects),
        args.output,
        args.edges_output,
    )
    print(json.dumps({"objects": objects}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())