"""
Moving an annotation as a whole (Select tool: drag the body of an annotation).

All data is normalized [0, 1]. Brush masks and semantic layers live in PNG
files and image labels have no geometry — they are not movable.
"""
from __future__ import annotations

import copy

from annotator.domain.annotation import AnnotationType

MOVABLE = {AnnotationType.BBOX, AnnotationType.OBB, AnnotationType.POINT,
           AnnotationType.SEGMENT, AnnotationType.POLYLINE, AnnotationType.POSE}


def _bounds(kind: AnnotationType, d: dict) -> tuple[float, float, float, float] | None:
    """(min x, min y, max x, max y) of what has to stay inside the image."""
    try:
        if kind == AnnotationType.BBOX:
            return d["x"], d["y"], d["x"] + d["w"], d["y"] + d["h"]
        if kind in (AnnotationType.OBB,):                  # keep the centre inside
            return d["cx"], d["cy"], d["cx"], d["cy"]
        if kind == AnnotationType.POINT:
            return d["x"], d["y"], d["x"], d["y"]
        if kind in (AnnotationType.SEGMENT, AnnotationType.POLYLINE):
            pts = d["points"]
        elif kind == AnnotationType.POSE:
            pts = [(x, y) for x, y, v in d["keypoints"] if v > 0]
        else:
            return None
        if not pts:
            return None
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)
    except (KeyError, TypeError, ValueError):
        return None


def clamp_shift(kind: AnnotationType, data: dict, dx: float, dy: float) -> tuple[float, float]:
    """The shift limited so the annotation stays inside the image."""
    b = _bounds(kind, data)
    if b is None:
        return 0.0, 0.0
    x0, y0, x1, y1 = b
    dx = min(max(dx, -x0), 1.0 - x1) if x1 - x0 <= 1 else 0.0
    dy = min(max(dy, -y0), 1.0 - y1) if y1 - y0 <= 1 else 0.0
    return dx, dy


def move_data(kind: AnnotationType, data: dict, dx: float, dy: float) -> dict:
    """A copy of `data` shifted by (dx, dy) — attributes, subclass and the
    rest are kept; a crack's source polyline moves along."""
    out = copy.deepcopy(data)
    if kind == AnnotationType.BBOX or kind == AnnotationType.POINT:
        out["x"] += dx
        out["y"] += dy
    elif kind == AnnotationType.OBB:
        out["cx"] += dx
        out["cy"] += dy
    elif kind in (AnnotationType.SEGMENT, AnnotationType.POLYLINE):
        out["points"] = [[x + dx, y + dy] for x, y in out["points"]]
    elif kind == AnnotationType.POSE:
        out["keypoints"] = [[x + dx, y + dy, v] if v > 0 else [x, y, v]
                            for x, y, v in out["keypoints"]]
    src = out.get("source_geometry")
    if isinstance(src, dict) and isinstance(src.get("points"), list):
        src["points"] = [[x + dx, y + dy] for x, y in src["points"]]
    return out
