"""Bounded local capture and YOLO adapters for live cameras and paced video replay."""

from __future__ import annotations

import hashlib
import logging
import multiprocessing as mp
import os
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, Full
from time import monotonic
from typing import Any

from .config import Capture, Perception, Source
from .contracts import Frame, RawDetection, RawInference

logger = logging.getLogger(__name__)


def frame_quality(payload: Any, settings: Capture) -> bool:
    """Reject empty, nonfinite, near-black, near-white, or textureless frames."""
    import cv2
    import numpy as np

    if payload is None or payload.size == 0 or not np.isfinite(payload).all():
        return False
    gray = cv2.cvtColor(payload, cv2.COLOR_BGR2GRAY)
    return (settings.minBrightness <= float(gray.mean()) <= settings.maxBrightness
            and float(gray.std()) >= settings.minContrast)


def _capture_worker(source: Source, uri: str, settings: Capture, stride: int,
                    frames: Any, stop: Any, heartbeat: Any, initial_epoch: int) -> None:
    heartbeat.value = monotonic()
    if source.type == "rtsp":
        with open(os.devnull, "w") as null:
            os.dup2(null.fileno(), 2)
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    import cv2

    sequence = 0
    dropped = 0
    epoch = initial_epoch

    def offer(frame: Frame) -> None:
        nonlocal dropped
        try:
            frames.put_nowait(frame)
        except Full:
            try:
                frames.get_nowait()
                dropped += 1
            except Empty:
                pass
            try:
                frames.put_nowait(frame)
            except Full:
                dropped += 1

    while not stop.is_set():
        capture = cv2.VideoCapture()
        try:
            heartbeat.value = monotonic()
            params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, settings.timeoutMilliseconds,
                      cv2.CAP_PROP_READ_TIMEOUT_MSEC, settings.timeoutMilliseconds]
            opened = capture.open(uri, cv2.CAP_FFMPEG, params)
            if not opened:
                raise ConnectionError("capture unavailable")
            fps = capture.get(cv2.CAP_PROP_FPS)
            interval = 1 / fps if 0 < fps <= 120 else 1 / 25
            while not stop.is_set():
                started = monotonic()
                heartbeat.value = started
                captured = datetime.now(UTC).isoformat()
                success, payload = capture.read()
                sequence += 1
                if not success:
                    raise ConnectionError("capture unavailable")
                if sequence % stride == 0:
                    offer(Frame(source.id, sequence, captured, payload, {
                        "usable": frame_quality(payload, settings), "epoch": epoch,
                        "droppedFrames": dropped, "readMilliseconds": (monotonic() - started) * 1000,
                    }))
                if source.type == "replay":
                    stop.wait(max(0, interval - (monotonic() - started)))
        except (ConnectionError, OSError, ValueError, cv2.error):
            epoch += 1
            offer(Frame(source.id, sequence, datetime.now(UTC).isoformat(), None,
                        {"usable": False, "epoch": epoch, "droppedFrames": dropped}))
        finally:
            capture.release()
        if source.type == "replay":
            stop.wait()
        else:
            stop.wait(1)


class CameraCapture:
    """Keep at most one queued frame and isolate camera-specific diagnostics."""

    def __init__(self, source: Source, uri: str, settings: Capture, stride: int) -> None:
        self._context = mp.get_context("spawn")
        self._source = source
        self._uri = uri
        self._settings = settings
        self._stride = stride
        self._generation = 0
        self._deadline = max(5.0, settings.timeoutMilliseconds / 1000 + 2)
        self._frames = self._context.Queue(maxsize=1)
        self._stop = self._context.Event()
        self._heartbeat = self._context.Value("d", monotonic(), lock=False)
        self._process = None

    def start(self) -> None:
        """Start the private capture process."""
        self._heartbeat.value = monotonic()
        self._process = self._context.Process(target=_capture_worker,
            args=(self._source, self._uri, self._settings, self._stride, self._frames,
                  self._stop, self._heartbeat, self._generation), daemon=True)
        self._process.start()

    def read(self, timeout: float = 0.2) -> Frame | None:
        """Return the newest queued frame, or None while capture is unavailable."""
        if self._process is None:
            raise RuntimeError("Capture must be started before reading")
        if self._source.type == "rtsp" and monotonic() - self._heartbeat.value > self._deadline:
            self._process.terminate()
            self._process.join(timeout=2)
            self._frames.close()
            self._frames = self._context.Queue(maxsize=1)
            self._generation += 1_000_000
            self.start()
            return Frame(self._source.id, 0, datetime.now(UTC).isoformat(), None,
                         {"usable": False, "epoch": self._generation, "watchdogRestart": True})
        try:
            return self._frames.get(timeout=timeout)
        except Empty:
            if not self._process.is_alive():
                raise ConnectionError("Capture process stopped; check capture backend availability")
            return None

    def close(self) -> None:
        """Stop capture within its read deadline, terminating a stuck backend."""
        self._stop.set()
        if self._process is not None:
            self._process.join(timeout=3)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=2)
        self._frames.close()


def normalize_detections(result: Any) -> list[RawDetection]:
    """Normalize YOLO box geometry to [0, 1] xyxy independent of frame size."""
    if result.boxes is None:
        raise ValueError("Model did not return detection boxes")
    boxes = result.boxes.xyxyn.cpu().tolist()
    confidences = result.boxes.conf.cpu().tolist()
    classes = result.boxes.cls.int().cpu().tolist()
    return [RawDetection(class_id, result.names[class_id], float(confidence),
                         dict(zip(("xMin", "yMin", "xMax", "yMax"), box, strict=True)))
            for box, confidence, class_id in zip(boxes, confidences, classes, strict=True)]


class YoloProvider:
    """Load local detection weights; fail early if required labels are unsupported."""

    def __init__(self, settings: Perception, confidence: float) -> None:
        import torch
        import ultralytics
        from ultralytics import YOLO

        path = Path(settings.model)
        if not path.is_file():
            raise ValueError("Configured model file is missing; provide trusted local detection weights")
        torch.set_num_threads(settings.threads)
        self._model = YOLO(path, task="detect")
        if self._model.task != "detect":
            raise ValueError("Configured model must support object detection")
        if not set(settings.labels).issubset(set(self._model.names.values())):
            raise ValueError("Configured labels are not supported by this model; choose matching weights or labels")
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        self.identity = f"{path.name}:sha256:{digest}"
        self.provider = f"ultralytics:{ultralytics.__version__}"
        self.settings = settings
        self.confidence = confidence

    def infer(self, frame: Frame) -> RawInference:
        """Emit explicit failure instead of interpreting provider errors as absence."""
        import cv2

        succeeded = False
        detections = []
        started = monotonic()
        try:
            results = self._model.predict(frame.payload, conf=self.confidence,
                                          imgsz=self.settings.imageSize, device=self.settings.device,
                                          verbose=False)
            detections = normalize_detections(results[0])
            succeeded = True
        except (RuntimeError, ValueError, TypeError, IndexError, AttributeError, OSError, cv2.error):
            logger.warning("Inference failed for source=%s; evidence unavailable", frame.source_id)
        return RawInference(
            inference_id=f"{frame.source_id}:{frame.sequence}", source_id=frame.source_id,
            sequence=frame.sequence, captured_at=frame.captured_at,
            produced_at=datetime.now(UTC).isoformat(), provider=self.provider, model=self.identity,
            detections=detections, succeeded=succeeded,
            metadata={"inferenceMilliseconds": (monotonic() - started) * 1000},
        )