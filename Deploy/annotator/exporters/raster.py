"""
Shared raster helpers for mask-based exporters (COCO RLE, COCO Panoptic).

rasterize()   — Annotation → (H,W) bool mask, pixel-exact for MASK / SEMANTIC
rle_encode()  — bool mask → COCO compressed RLE {"size": [H, W], "counts": str}
rle_decode()  — inverse of rle_encode (used by tests / round-trip checks)

The RLE string format is the one written by pycocotools (column-major run
lengths, delta-coded against the run two positions back, 5-bit LEB128-style
chunks offset by ASCII 48), so files load with pycocotools, Detectron2,
MMDetection, etc. without this project installing pycocotools itself.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image as PilImage, ImageDraw

from annotator.domain.annotation import Annotation, AnnotationType

# Annotation types that cover an area (or a thick line) and can be rasterized.
RASTER_TYPES = {AnnotationType.MASK, AnnotationType.SEMANTIC, AnnotationType.SEGMENT,
                AnnotationType.POLYLINE, AnnotationType.BBOX, AnnotationType.OBB}
# Class annotation_type values whose annotations are rasterizable.
RASTER_CLASS_TYPES = {"mask", "semantic", "polygon", "polyline", "bbox", "obb"}


def polyline_width(w: int, h: int) -> int:
    """Adaptive thickness for POLYLINE (cracks) — same rule as Semantic Masks."""
    return max(3, min(w, h) // 150)


def load_png_mask(ann: Annotation, w: int, h: int,
                  project_path: Path | None) -> np.ndarray | None:
    """Bool mask from the annotation's PNG, resized to (h, w); None if unavailable."""
    rel = ann.data.get("mask_png_path")
    if not rel or project_path is None:
        return None
    src = Path(project_path) / rel
    if not src.exists():
        return None
    with PilImage.open(src) as im:
        m = im.convert("L")
    if m.size != (w, h):
        m = m.resize((w, h), PilImage.Resampling.NEAREST)
    return np.asarray(m) > 0


def rasterize(ann: Annotation, w: int, h: int,
              project_path: Path | None) -> np.ndarray | None:
    """Return a (h, w) bool mask of the annotation, or None if not rasterizable."""
    t = ann.ann_type
    if t not in RASTER_TYPES:
        return None

    if t in (AnnotationType.MASK, AnnotationType.SEMANTIC):
        m = load_png_mask(ann, w, h, project_path)
        if m is not None:
            return m

    img = PilImage.new("L", (w, h), 0)
    draw = ImageDraw.Draw(img)
    d = ann.data

    def px(points):
        return [(x * w, y * h) for x, y in points]

    if t == AnnotationType.MASK:
        pts = px(d.get("polygon", []))
        if len(pts) >= 3:
            draw.polygon(pts, fill=255)
    elif t == AnnotationType.SEMANTIC:
        for poly in d.get("polygons", []):
            if len(poly) >= 3:
                draw.polygon(px(poly), fill=255)
    elif t == AnnotationType.SEGMENT:
        pts = px(d.get("points", []))
        if len(pts) >= 3:
            draw.polygon(pts, fill=255)
    elif t == AnnotationType.POLYLINE:
        pts = px(d.get("points", []))
        if len(pts) >= 2:
            draw.line(pts, fill=255, width=polyline_width(w, h))
    elif t == AnnotationType.BBOX:
        x0, y0 = d["x"] * w, d["y"] * h
        draw.rectangle([x0, y0, x0 + d["w"] * w, y0 + d["h"] * h], fill=255)
    elif t == AnnotationType.OBB:
        draw.polygon(obb_corners(d, w, h), fill=255)
    return np.asarray(img) > 0


def obb_corners(d: dict, w: int, h: int) -> list[tuple[float, float]]:
    cx, cy = d["cx"] * w, d["cy"] * h
    hw, hh = d["w"] * w / 2, d["h"] * h / 2
    rad = math.radians(d.get("angle_deg", 0.0))
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    return [(cx + cos_a * lx - sin_a * ly, cy + sin_a * lx + cos_a * ly)
            for lx, ly in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]]


def bbox_xywh(mask: np.ndarray) -> list[float]:
    """COCO bbox [x, y, w, h] in pixels of the non-zero area ([0,0,0,0] if empty)."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return [0.0, 0.0, 0.0, 0.0]
    x0, y0 = int(xs.min()), int(ys.min())
    return [float(x0), float(y0),
            float(int(xs.max()) - x0 + 1), float(int(ys.max()) - y0 + 1)]


# ── COCO RLE ──────────────────────────────────────────────────────────────────

def _run_lengths(mask: np.ndarray) -> list[int]:
    """Column-major run lengths, starting with a (possibly empty) run of zeros."""
    flat = np.asarray(mask, dtype=bool).flatten(order="F")
    if flat.size == 0:
        return [0]
    change = np.flatnonzero(flat[1:] != flat[:-1]) + 1
    bounds = np.concatenate(([0], change, [flat.size]))
    runs = np.diff(bounds).tolist()
    if flat[0]:
        runs.insert(0, 0)
    return runs


def _counts_to_string(counts: list[int]) -> str:
    out = []
    for i, x in enumerate(counts):
        if i > 2:
            x -= counts[i - 2]
        more = True
        while more:
            c = x & 0x1F
            x >>= 5                       # arithmetic shift, like the C original
            more = (x != -1) if (c & 0x10) else (x != 0)
            if more:
                c |= 0x20
            out.append(chr(c + 48))
    return "".join(out)


def _string_to_counts(s: str) -> list[int]:
    counts: list[int] = []
    p = 0
    while p < len(s):
        x = k = 0
        more = True
        while more:
            c = ord(s[p]) - 48
            x |= (c & 0x1F) << (5 * k)
            more = bool(c & 0x20)
            p += 1
            k += 1
            if not more and (c & 0x10):
                x |= -1 << (5 * k)
        if len(counts) > 2:
            x += counts[-2]
        counts.append(x)
    return counts


def rle_encode(mask: np.ndarray) -> dict:
    h, w = mask.shape
    return {"size": [int(h), int(w)],
            "counts": _counts_to_string(_run_lengths(mask))}


def rle_decode(rle: dict) -> np.ndarray:
    h, w = rle["size"]
    counts = rle["counts"]
    if isinstance(counts, str):
        counts = _string_to_counts(counts)
    flat = np.zeros(h * w, dtype=bool)
    pos, val = 0, False
    for n in counts:
        if val:
            flat[pos:pos + n] = True
        pos += n
        val = not val
    return flat.reshape((w, h)).T      # back from column-major
