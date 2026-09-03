"""CLI smoke test: capture a camera frame and analyze it with a local VLM.

Runs an on-device vision-language model against a live RTSP frame, or against
a saved image file, to verify the perception runtime works end-to-end before
wiring it into a PerceptionWorkload.

Two backends are available:
  - foundry (default): Foundry Local / ONNX Runtime GenAI. CPU-only on this
    Mac today -- the WebGPU (Metal) execution provider is cataloged but
    errors with "not supported in this build" on Foundry Local 0.10.3 /
    foundry-local-sdk 2.0.1. Model load is ~45s per process since there's
    no persistent server.
  - mlx: MLX-VLM, which genuinely runs on the Apple Silicon GPU via Metal
    (mx.default_device() reports gpu). Much faster: ~3s cached model load,
    ~100+ tok/s generation.

Usage:
    export TAPO_USERNAME=... TAPO_PASSWORD=...
    python scripts/vision_check.py --host 10.0.0.12
    python scripts/vision_check.py --image path/to/frame.jpg
    python scripts/vision_check.py --save-frame out.jpg --prompt "Count the vehicles."
    python scripts/vision_check.py --backend mlx --prompt "What color is the car?"
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
from pathlib import Path

import cv2

from tiger_poc.capture import CameraConfig, CameraConnectionError, RtspCamera
from tiger_poc.capture.image_correction import reduce_window_glare

logger = logging.getLogger("vision_check")

DEFAULT_MODEL_ALIAS = {
    "foundry": "qwen3-vl-2b-instruct",
    "mlx": "mlx-community/Qwen2-VL-2B-Instruct-4bit",
}
DEFAULT_APP_NAME = "tiger-poc-vision-check"  # fixed so the model cache is reused across runs
DEFAULT_PROMPT = (
    "Describe what you see in this security camera frame. Mention any "
    "animals, people, or notable objects and roughly where they are in "
    "the frame."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image", help="Analyze this image file instead of capturing from the camera"
    )
    parser.add_argument("--host", default=None, help="Defaults to TAPO_HOST")
    parser.add_argument("--quality", choices=("hd", "sd"), default="hd")
    parser.add_argument("--save-frame", help="Write the captured frame to this path")
    parser.add_argument(
        "--deglare",
        action="store_true",
        help="Reduce broad window glare before saving or analyzing the frame",
    )
    parser.add_argument(
        "--backend",
        choices=("foundry", "mlx"),
        default="foundry",
        help="Inference backend: 'foundry' (Foundry Local, CPU) or 'mlx' (MLX-VLM, Metal GPU)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model alias/repo for the chosen backend (defaults per-backend)",
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    return parser.parse_args()


def capture_frame(
    host: str | None,
    quality: str,
    save_frame: str | None,
    deglare: bool,
) -> bytes:
    """Grab a single frame from the RTSP camera and return it JPEG-encoded."""
    try:
        config = CameraConfig.from_env(host=host, quality=quality)
    except ValueError as exc:
        logger.error("%s", exc)
        raise SystemExit(2) from exc

    try:
        with RtspCamera(config) as camera:
            frame = next(iter(camera.iter_frames(max_frames=1)))
    except CameraConnectionError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc

    height, width = frame.image.shape[:2]
    logger.info("frame %d %dx%d at %s", frame.sequence, width, height, frame.timestamp.isoformat())

    image = reduce_window_glare(frame.image) if deglare else frame.image
    if save_frame:
        cv2.imwrite(save_frame, image)
        logger.info("Wrote %s", save_frame)

    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        logger.error("Failed to JPEG-encode captured frame")
        raise SystemExit(1)
    return encoded.tobytes()


def analyze_image_foundry(model_alias: str, prompt: str, image_bytes: bytes, image_format: str) -> str:
    """Run a single-turn vision inference request against a local Foundry Local model.

    Uses the native ChatSession API (foundry-local-sdk v2.0.1+), which differs
    from the OpenAI-wrapper pattern shown in Microsoft's public docs. The
    response comes back as a MessageItem whose text lives in a nested TextItem
    part, not on the MessageItem itself.
    """
    from foundry_local_sdk import Configuration, FoundryLocalManager
    from foundry_local_sdk.items import ImageItem, MessageItem, MessageRole, TextItem
    from foundry_local_sdk.request import Request
    from foundry_local_sdk.session import ChatSession

    manager = FoundryLocalManager.instance
    if manager is None:
        FoundryLocalManager.initialize(Configuration(app_name=DEFAULT_APP_NAME))
        manager = FoundryLocalManager.instance
        assert manager is not None

    model = manager.catalog.get_model(model_alias)
    if model is None:
        raise SystemExit(f"Model '{model_alias}' not found in catalog.")

    if not model.is_cached:
        logger.info("Downloading %s...", model_alias)
        model.download(lambda pct: print(f"\r  {pct:.1f}%", end="", flush=True))
        print()

    logger.info("Loading %s...", model_alias)
    model.load()

    try:
        with ChatSession(model) as session:
            message = MessageItem(
                MessageRole.USER,
                [ImageItem(image_format, image_bytes), TextItem(prompt)],
            )
            with Request() as request:
                request.add_item(message)
                with session.process_request(request) as response:
                    texts = [
                        part.text
                        for i in range(response.item_count)
                        for part in getattr(response.get_item(i), "_parts", [response.get_item(i)])
                        if getattr(part, "text", None)
                    ]
        return "\n".join(texts)
    finally:
        model.unload()
        manager.close()


def analyze_image_mlx(model_path: str, prompt: str, image_bytes: bytes) -> str:
    """Run a single-turn vision inference request against a local MLX-VLM model.

    Runs natively on the Apple Silicon GPU via Metal (mlx.core.default_device()
    reports gpu) instead of Foundry Local's CPU-only path on this Mac. Cached
    model load is ~3s vs. Foundry Local's ~45s per-process load.
    """
    from mlx_vlm import generate, load
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.utils import load_config
    from PIL import Image

    logger.info("Loading %s...", model_path)
    model, processor = load(model_path)
    config = load_config(model_path)

    image = [Image.open(io.BytesIO(image_bytes)).convert("RGB")]
    formatted_prompt = apply_chat_template(processor, config, prompt, num_images=len(image))
    result = generate(model, processor, formatted_prompt, image, verbose=False, max_tokens=512)
    return result.text


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    model = args.model or DEFAULT_MODEL_ALIAS[args.backend]

    if args.image:
        image_path = Path(args.image)
        if not image_path.is_file():
            logger.error("Image not found: %s", image_path)
            return 2
        image_bytes = image_path.read_bytes()
        image_format = image_path.suffix.lstrip(".").lower() or "jpeg"
        if image_format == "jpg":
            image_format = "jpeg"
    else:
        image_bytes = capture_frame(
            args.host, args.quality, args.save_frame, args.deglare
        )
        image_format = "jpeg"

    if args.backend == "mlx":
        description = analyze_image_mlx(model, args.prompt, image_bytes)
    else:
        description = analyze_image_foundry(model, args.prompt, image_bytes, image_format)
    if not description:
        logger.error("Model returned no text")
        return 1

    print(description)
    logger.info("OK: analyzed frame with %s (%s)", model, args.backend)
    return 0


if __name__ == "__main__":
    sys.exit(main())
