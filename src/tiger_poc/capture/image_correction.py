"""Small, non-destructive corrections for images captured through glass."""

from __future__ import annotations

import cv2
import numpy as np


def reduce_window_glare(image: np.ndarray) -> np.ndarray:
    """Reduce broad window glare while preserving the original image pixels.

    This corrects uneven illumination and restores local contrast. It cannot
    reconstruct details hidden by a reflection, so the result is intended for
    preview and model input rather than archival capture.
    """
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image must be a BGR color image")

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness, channel_a, channel_b = cv2.split(lab)
    illumination = cv2.GaussianBlur(lightness, (0, 0), sigmaX=35, sigmaY=35)
    target = float(np.median(illumination))
    gain = target / np.maximum(illumination.astype(np.float32), 1.0)
    gain = np.clip(gain, 0.65, 1.6)
    corrected_lightness = np.clip(lightness.astype(np.float32) * gain, 0, 255)
    corrected_lightness = corrected_lightness.astype(np.uint8)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    corrected_lightness = clahe.apply(corrected_lightness)
    corrected_lab = cv2.merge((corrected_lightness, channel_a, channel_b))
    return cv2.cvtColor(corrected_lab, cv2.COLOR_LAB2BGR)