"""
YOLO segmentation auto-exporter.

Writes one .txt file per image into a labels/ folder alongside the images:

  If images live in a folder named "images" (or "imgs" / "img" / "photos"):
    .../dataset/images/img.jpg  →  .../dataset/labels/img.txt   (standard YOLO)
  Otherwise:
    .../myfolder/img.jpg        →  .../myfolder/labels/img.txt

Line format per annotation:
  SEGMENT / POLYLINE → class_id  x1 y1 x2 y2 ... xn yn   (YOLO seg polygon)
  BBOX               → class_id  x1 y1 x2 y2 x3 y3 x4 y4 (4-corner polygon)

All coordinates are normalized [0, 1] as required by YOLO.
"""
from __future__ import annotations

from pathlib import Path

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.project import Project
from annotator.exporters.base import BaseExporter, write_yolo_dataset

_IMG_FOLDER_NAMES = {"images", "imgs", "img", "photos"}


def _labels_dir(image_path: str) -> Path:
    """Resolve the labels/ directory for a given image path."""
    p = Path(image_path)
    if p.parent.name.lower() in _IMG_FOLDER_NAMES:
        return p.parent.parent / "labels"
    return p.parent / "labels"


def _format_annotation(ann: Annotation) -> str | None:
    """Return a YOLO-format string for one annotation, or None to skip."""
    if ann.ann_type in (AnnotationType.SEGMENT, AnnotationType.POLYLINE):
        pts = ann.data.get("points", [])
        if len(pts) < 2:
            return None
        coords = " ".join(f"{x:.6f} {y:.6f}" for x, y in pts)
        return f"{ann.class_id} {coords}"

    if ann.ann_type == AnnotationType.MASK:
        pts = ann.data.get("polygon", [])
        if len(pts) < 3:
            return None
        coords = " ".join(f"{x:.6f} {y:.6f}" for x, y in pts)
        return f"{ann.class_id} {coords}"

    if ann.ann_type == AnnotationType.BBOX:
        d = ann.data
        x, y, w, h = d["x"], d["y"], d["w"], d["h"]
        # Convert to 4-corner polygon (TL → TR → BR → BL)
        corners = [
            (x,     y    ),
            (x + w, y    ),
            (x + w, y + h),
            (x,     y + h),
        ]
        coords = " ".join(f"{cx:.6f} {cy:.6f}" for cx, cy in corners)
        return f"{ann.class_id} {coords}"

    return None   # future types (OBB, POSE, …) — skip silently


class YoloSegExporter(BaseExporter):
    """Implements BaseExporter for full-project export (Phase 5)."""

    @property
    def name(self) -> str:
        return "YOLO Segmentation"

    @property
    def file_extension(self) -> str:
        return ".txt"

    def export(self, project: Project, output_dir: Path, **kwargs):
        write_yolo_dataset(
            project,
            kwargs.get("all_annotations", {}),
            output_dir,
            _format_annotation,
            copy_images=kwargs.get("copy_images", True),
        )

    # ── per-image auto-export (Phase 2) ───────────────────────────────────────

    @staticmethod
    def export_image(image_path: str,
                     annotations: list[Annotation],
                     project: Project) -> Path:
        """
        Write (or overwrite) the YOLO .txt file for one image.
        Always writes the file so deletions are reflected (empty file = no annotations).
        Returns the path that was written.
        """
        labels_dir = _labels_dir(image_path)
        labels_dir.mkdir(parents=True, exist_ok=True)

        out_path = labels_dir / (Path(image_path).stem + ".txt")

        lines = []
        for ann in annotations:
            line = _format_annotation(ann)
            if line:
                lines.append(line)

        out_path.write_text("\n".join(lines), encoding="utf-8")
        return out_path
