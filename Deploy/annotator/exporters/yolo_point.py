"""
YOLO Point exporter.

Exports POINT annotations as YOLO keypoints format with a single keypoint
and a synthetic 1%×1% bounding box centered on the point.

Line format:
  class_id cx cy 0.01 0.01 x y 2

data.yaml is extended with:
  kpt_shape: [1, 3]
"""
from __future__ import annotations

from pathlib import Path

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.exporters.base import BaseExporter, write_yolo_dataset

_BBOX_SIZE = 0.01   # synthetic bbox side length (1% of image)


def _format(ann: Annotation) -> str | None:
    if ann.ann_type != AnnotationType.POINT:
        return None
    x = ann.data.get("x", 0.0)
    y = ann.data.get("y", 0.0)
    cx = max(_BBOX_SIZE / 2, min(1.0 - _BBOX_SIZE / 2, x))
    cy = max(_BBOX_SIZE / 2, min(1.0 - _BBOX_SIZE / 2, y))
    return f"{ann.class_id} {cx:.6f} {cy:.6f} {_BBOX_SIZE:.6f} {_BBOX_SIZE:.6f} {x:.6f} {y:.6f} 2"


class YoloPointExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "YOLO Point"

    @property
    def file_extension(self) -> str:
        return ".txt"

    def export(self, project, output_dir: Path, **kwargs):
        output_dir = Path(output_dir)
        write_yolo_dataset(
            project,
            kwargs.get("all_annotations", {}),
            output_dir,
            _format,
            copy_images=kwargs.get("copy_images", True),
        )
        yaml_path = output_dir / "data.yaml"
        with open(yaml_path, "a", encoding="utf-8") as f:
            f.write("\nkpt_shape: [1, 3]\n")
