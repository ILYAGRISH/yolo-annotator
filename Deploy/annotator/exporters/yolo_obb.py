"""
YOLO OBB exporter.

Label format per line (ultralytics OBB):
  class_id  x1 y1  x2 y2  x3 y3  x4 y4
Where (x1,y1)…(x4,y4) are the four rotated corners in TL→TR→BR→BL order,
all coordinates normalized [0, 1].

Only OBB annotations are exported; other types are silently skipped.
"""
from __future__ import annotations

import math
from pathlib import Path

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.project import Project
from annotator.exporters.base import BaseExporter, write_yolo_dataset


def _rotate_pt(px: float, py: float,
               cx: float, cy: float, angle_deg: float) -> tuple[float, float]:
    """Rotate (px, py) clockwise around (cx, cy) by angle_deg."""
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    dx, dy = px - cx, py - cy
    return (cx + cos_a * dx - sin_a * dy,
            cy + sin_a * dx + cos_a * dy)


def _format_obb(ann: Annotation) -> str | None:
    if ann.ann_type != AnnotationType.OBB:
        return None
    d = ann.data
    cx, cy = d["cx"], d["cy"]
    hw, hh = d["w"] / 2, d["h"] / 2
    angle = d.get("angle_deg", 0.0)
    # TL, TR, BR, BL in OBB-local space, then rotate
    local = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    corners = [_rotate_pt(cx + lx, cy + ly, cx, cy, angle) for lx, ly in local]
    pts = " ".join(f"{x:.6f} {y:.6f}" for x, y in corners)
    return f"{ann.class_id} {pts}"


class YoloObbExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "YOLO OBB"

    @property
    def file_extension(self) -> str:
        return ".txt"

    def export(self, project: Project, output_dir: Path, **kwargs):
        write_yolo_dataset(
            project,
            kwargs.get("all_annotations", {}),
            output_dir,
            _format_obb,
            copy_images=kwargs.get("copy_images", True),
        )
