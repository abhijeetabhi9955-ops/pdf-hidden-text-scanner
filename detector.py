"""Rule-based PDF hidden-text scanning used by the Streamlit app.

This module finds potentially hidden text. It does not decide whether a
document or user is malicious; every flagged span requires human review.
"""

from __future__ import annotations

import math
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np


def _int_to_rgb(color: int) -> tuple[int, int, int]:
    return ((color >> 16) & 255, (color >> 8) & 255, color & 255)


def _rgb_distance(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


def _to_pixel_rect(
    rect: fitz.Rect, page_rect: fitz.Rect, image_width: int, image_height: int
) -> tuple[int, int, int, int] | None:
    """Map a PDF rectangle in points to its rendered-image rectangle in pixels."""
    x_scale = image_width / page_rect.width
    y_scale = image_height / page_rect.height
    x0 = max(0, min(image_width, int(math.floor((rect.x0 - page_rect.x0) * x_scale))))
    y0 = max(0, min(image_height, int(math.floor((rect.y0 - page_rect.y0) * y_scale))))
    x1 = max(0, min(image_width, int(math.ceil((rect.x1 - page_rect.x0) * x_scale))))
    y1 = max(0, min(image_height, int(math.ceil((rect.y1 - page_rect.y0) * y_scale))))
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def _local_background(
    pixels: np.ndarray, pixel_rect: tuple[int, int, int, int], padding: int = 5
) -> tuple[int, int, int] | None:
    """Estimate the background colour from a thin ring around a text span."""
    x0, y0, x1, y1 = pixel_rect
    height, width, _ = pixels.shape
    left, top = max(0, x0 - padding), max(0, y0 - padding)
    right, bottom = min(width, x1 + padding), min(height, y1 + padding)

    parts = []
    if top < y0:
        parts.append(pixels[top:y0, left:right])
    if y1 < bottom:
        parts.append(pixels[y1:bottom, left:right])
    if left < x0:
        parts.append(pixels[y0:y1, left:x0])
    if x1 < right:
        parts.append(pixels[y0:y1, x1:right])
    parts = [part.reshape(-1, 3) for part in parts if part.size]
    if not parts:
        return None

    rgb = np.median(np.concatenate(parts, axis=0), axis=0)
    return tuple(int(value) for value in rgb)


def _ink_density(
    pixels: np.ndarray,
    pixel_rect: tuple[int, int, int, int],
    background: tuple[int, int, int],
    difference: float = 30.0,
) -> float:
    """Measure how much of a span's rendered region visibly differs from its background."""
    x0, y0, x1, y1 = pixel_rect
    crop = pixels[y0:y1, x0:x1].astype(np.float32)
    if crop.size == 0:
        return 0.0
    distances = np.linalg.norm(crop - np.asarray(background, dtype=np.float32), axis=2)
    return float(np.mean(distances >= difference))


def _render_pixels(page: fitz.Page, zoom: float = 2.0) -> np.ndarray:
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8)
    return image.reshape(pixmap.height, pixmap.width, pixmap.n)[:, :, :3]


def scan_pdf(
    pdf_path: Path,
    min_font_size: float = 4.0,
    color_threshold: float = 25.0,
    min_ink_density: float = 0.015,
) -> list[dict]:
    """Return all text spans that match at least one visibility-risk rule."""
    findings: list[dict] = []

    with fitz.open(pdf_path) as document:
        for page_number, page in enumerate(document, start=1):
            page_rect = page.rect
            pixels = _render_pixels(page)
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:  # 0 means a text block.
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue

                        bbox = fitz.Rect(span["bbox"])
                        font_size = float(span.get("size", 0))
                        text_rgb = _int_to_rgb(int(span.get("color", 0)))
                        reasons: list[str] = []
                        if font_size < min_font_size:
                            reasons.append(f"Small font: {font_size:.2f} pt")
                        if not page_rect.intersects(bbox):
                            reasons.append("Text is outside the visible page")

                        background_rgb = None
                        colour_gap = None
                        visible_ink = None
                        pixel_rect = _to_pixel_rect(
                            bbox, page_rect, pixels.shape[1], pixels.shape[0]
                        )
                        if pixel_rect is not None:
                            background_rgb = _local_background(pixels, pixel_rect)
                        if background_rgb is not None:
                            colour_gap = _rgb_distance(text_rgb, background_rgb)
                            if colour_gap < color_threshold:
                                reasons.append(
                                    f"Text closely matches local background (RGB distance {colour_gap:.1f})"
                                )
                            visible_ink = _ink_density(pixels, pixel_rect, background_rgb)
                            if visible_ink < min_ink_density:
                                reasons.append(f"Very low visible ink ({visible_ink:.2%})")

                        if reasons:
                            findings.append(
                                {
                                    "page": page_number,
                                    "text": text,
                                    "font": span.get("font", "unknown"),
                                    "font_size_pt": round(font_size, 2),
                                    "text_rgb": text_rgb,
                                    "background_rgb": background_rgb,
                                    "color_distance": round(colour_gap, 2)
                                    if colour_gap is not None
                                    else None,
                                    "ink_density": round(visible_ink, 5)
                                    if visible_ink is not None
                                    else None,
                                    "bbox": [round(value, 2) for value in bbox],
                                    "reasons": reasons,
                                }
                            )
    return findings
