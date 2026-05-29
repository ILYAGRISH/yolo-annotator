"""
YOLO detect exporter.

Label format per line:
  class_id  cx  cy  w  h
All values normalized [0, 1].

Only BBOX annotations are exported; other types are silently skipped.
"""
from __future__ import annotations

from pathlib import Path

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.project import Project
from annotator.exporters.base import BaseExporter, write_yolo_dataset


def _format_detect(ann: Annotation) -> str | None:
    if ann.ann_type != AnnotationType.BBOX:
        return None
    d = ann.data
    cx = d["x"] + d["w"] / 2
    cy = d["y"] + d["h"] / 2
    return f"{ann.class_id} {cx:.6f} {cy:.6f} {d['w']:.6f} {d['h']:.6f}"


class YoloDetectExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "YOLO Detect"

    @property
    def file_extension(self) -> str:
        return ".txt"

    def export(self, project: Project, output_dir: Path, **kwargs):
        write_yolo_dataset(
            project,
            kwargs.get("all_annotations", {}),
            output_dir,
            _format_detect,
            copy_images=kwargs.get("copy_images", True),
        )
