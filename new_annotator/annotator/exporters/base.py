import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from annotator.domain.project import Project


# ── shared YOLO-style dataset writer ─────────────────────────────────────────

def write_yolo_dataset(project: Project,
                        all_annotations: dict,
                        output_dir: Path,
                        ann_to_line_fn,
                        copy_images: bool = True) -> None:
    """
    Write a YOLO-style dataset:
      output_dir/
        images/{split}/...
        labels/{split}/...
        data.yaml

    ann_to_line_fn(ann) -> str | None
      Return a formatted label line or None to skip the annotation.
    """
    output_dir = Path(output_dir)

    for img_rec in project.images:
        split = img_rec.split or "train"
        img_path = Path(img_rec.path)
        anns = all_annotations.get(img_rec.path, [])

        labels_dir = output_dir / "labels" / split
        labels_dir.mkdir(parents=True, exist_ok=True)
        lines = [ln for ann in anns for ln in [ann_to_line_fn(ann)] if ln]
        (labels_dir / (img_path.stem + ".txt")).write_text(
            "\n".join(lines), encoding="utf-8")

        if copy_images and img_path.exists():
            images_dir = output_dir / "images" / split
            images_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(img_path, images_dir / img_path.name)

    _write_data_yaml(project, output_dir)


def _write_data_yaml(project: Project, output_dir: Path) -> None:
    splits = sorted({r.split or "train" for r in project.images})
    names = [c.name for c in sorted(project.classes, key=lambda c: c.id)]
    lines = [f"path: {output_dir.resolve()}"]
    for s in ("train", "val", "test"):
        if s in splits:
            lines.append(f"{s}: images/{s}")
    lines.append(f"nc: {len(names)}")
    lines.append(f"names: {names}")
    (output_dir / "data.yaml").write_text("\n".join(lines), encoding="utf-8")


# ── abstract base ─────────────────────────────────────────────────────────────

class BaseExporter(ABC):
    """
    All export formats implement this interface.
    Exporters must NOT be imported in the base runtime until explicitly invoked.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name, e.g. 'YOLO Segmentation'."""

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Primary output extension, e.g. '.txt'."""

    @abstractmethod
    def export(self, project: Project, output_dir: Path, **kwargs):
        """Export the full project to output_dir."""
