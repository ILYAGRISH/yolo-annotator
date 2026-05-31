"""
YOLO detect exporter.

Label format per line:
  class_id  cx  cy  w  h
All values normalized [0, 1].

geometry_policy:
  "skip"    — only BBOX annotations exported (default)
  "convert" — MASK/POLYGON/SEGMENT → bounding box of their extent
"""
from __future__ import annotations

from pathlib import Path

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.project import Project
from annotator.exporters.base import BaseExporter, write_yolo_dataset


def _get_bbox_from_ann(ann: Annotation):
    """Compute (cx, cy, w, h) from a non-BBOX annotation, or return None."""
    if ann.ann_type == AnnotationType.MASK:
        b = ann.data.get("bbox")
        if b:
            x, y, w, h = b["x"], b["y"], b["w"], b["h"]
            if w > 0 and h > 0:
                return x + w / 2, y + h / 2, w, h
    if ann.ann_type in (AnnotationType.SEGMENT, AnnotationType.POLYLINE):
        pts = ann.data.get("points", [])
        if len(pts) >= 2:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            x, y = min(xs), min(ys)
            w, h = max(xs) - x, max(ys) - y
            if w > 0 and h > 0:
                return x + w / 2, y + h / 2, w, h
    return None


def _make_detect_fn(policy: str = "skip"):
    """Return ann→line function for YOLO detect with the given geometry_policy."""
    def _fmt(ann: Annotation) -> str | None:
        if ann.ann_type == AnnotationType.BBOX:
            d = ann.data
            cx = d["x"] + d["w"] / 2
            cy = d["y"] + d["h"] / 2
            return f"{ann.class_id} {cx:.6f} {cy:.6f} {d['w']:.6f} {d['h']:.6f}"
        if policy == "convert":
            bbox = _get_bbox_from_ann(ann)
            if bbox:
                cx, cy, w, h = bbox
                return f"{ann.class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"
        return None
    return _fmt


class YoloDetectExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "YOLO Detect"

    @property
    def file_extension(self) -> str:
        return ".txt"

    def export(self, project: Project, output_dir: Path, **kwargs):
        policy = kwargs.get("geometry_policy", "skip")
        write_yolo_dataset(
            project,
            kwargs.get("all_annotations", {}),
            output_dir,
            _make_detect_fn(policy),
            copy_images=kwargs.get("copy_images", True),
        )
