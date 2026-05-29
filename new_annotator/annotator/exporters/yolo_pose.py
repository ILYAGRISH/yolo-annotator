"""
YOLO Pose exporter.

Line format per annotation:
  class_id cx cy w h  kx1 ky1 v1  kx2 ky2 v2  ...

All coordinates are normalized [0, 1].
Bounding box (cx cy w h) is auto-computed from visible keypoints
with a 5% margin on each side (clamped to [0, 1]).

data.yaml is extended with:
  kpt_shape: [N, 3]     (N = skeleton length of the first keypoints class)
"""
from __future__ import annotations

from pathlib import Path

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.project import Project
from annotator.exporters.base import BaseExporter, write_yolo_dataset

_MARGIN = 0.05   # fractional margin around visible keypoints for auto-bbox


def _kpt_count_for_project(project: Project) -> int:
    """Return skeleton length from the first 'keypoints' class, or 0."""
    for cls in project.classes:
        if cls.annotation_type == "keypoints" and cls.skeleton:
            return len(cls.skeleton)
    return 0


def _make_format_fn(project: Project):
    """Return a closure that formats one POSE Annotation as a YOLO Pose line."""

    def _format(ann: Annotation) -> str | None:
        if ann.ann_type != AnnotationType.POSE:
            return None

        raw_kps: list[list[float]] = ann.data.get("keypoints", [])
        if not raw_kps:
            return None

        # Determine expected keypoint count from class skeleton
        cls = project.get_class(ann.class_id)
        n_kp = len(cls.skeleton) if (cls and cls.skeleton) else len(raw_kps)

        # Pad / trim to match skeleton length
        kps = [list(k) for k in raw_kps[:n_kp]]
        while len(kps) < n_kp:
            kps.append([0.0, 0.0, 0])

        # Compute bbox from visible keypoints
        visible = [(k[0], k[1]) for k in kps if int(k[2]) > 0]
        if not visible:
            return None   # nothing visible → skip

        xs = [p[0] for p in visible]
        ys = [p[1] for p in visible]
        xmin = max(0.0, min(xs) - _MARGIN)
        xmax = min(1.0, max(xs) + _MARGIN)
        ymin = max(0.0, min(ys) - _MARGIN)
        ymax = min(1.0, max(ys) + _MARGIN)
        cx = (xmin + xmax) / 2
        cy = (ymin + ymax) / 2
        w  = xmax - xmin
        h  = ymax - ymin

        kp_str = " ".join(
            f"{k[0]:.6f} {k[1]:.6f} {int(k[2])}" for k in kps)
        return f"{ann.class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f} {kp_str}"

    return _format


class YoloPoseExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "YOLO Pose"

    @property
    def file_extension(self) -> str:
        return ".txt"

    def export(self, project: Project, output_dir: Path, **kwargs):
        output_dir = Path(output_dir)
        write_yolo_dataset(
            project,
            kwargs.get("all_annotations", {}),
            output_dir,
            _make_format_fn(project),
            copy_images=kwargs.get("copy_images", True),
        )

        # Append kpt_shape to data.yaml
        n = _kpt_count_for_project(project)
        if n > 0:
            yaml_path = output_dir / "data.yaml"
            with open(yaml_path, "a", encoding="utf-8") as f:
                f.write(f"\nkpt_shape: [{n}, 3]\n")
