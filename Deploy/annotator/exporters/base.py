import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from annotator.domain.project import Project


# ── YOLO class indices and label lines ───────────────────────────────────────

def yolo_class_index(project: Project) -> dict[int, int]:
    """Project class id -> YOLO class index 0..nc-1, in the order of `names`
    in data.yaml (classes sorted by id). Ids have gaps once a class is
    deleted from the schema; YOLO needs 0..nc-1."""
    return {c.id: i for i, c in enumerate(sorted(project.classes, key=lambda c: c.id))}


def image_size(img_rec) -> tuple[int, int]:
    """(width, height) in pixels from the image record, else read from the
    file header; (0, 0) if unknown."""
    if img_rec is not None and img_rec.width > 0 and img_rec.height > 0:
        return img_rec.width, img_rec.height
    if img_rec is not None:
        try:
            from PIL import Image
            with Image.open(img_rec.path) as im:
                return im.width, im.height
        except Exception:                       # noqa: BLE001
            pass
    return 0, 0


def yolo_label_lines(anns, ann_to_line_fn, class_index: dict[int, int],
                     img_rec=None) -> list[str]:
    """Format annotations as YOLO label lines with YOLO class indices.

    Formatters write `ann.class_id` first on each line; it is replaced by the
    YOLO index here (a class missing from the project drops the line).
    A formatter with `uses_image_size = True` is called as fn(ann, (w, h))."""
    size = image_size(img_rec) if getattr(ann_to_line_fn, "uses_image_size", False) else None
    out = []
    for ann in anns:
        text = ann_to_line_fn(ann, size) if size is not None else ann_to_line_fn(ann)
        if not text:
            continue
        for line in text.split("\n"):
            cid, _, rest = line.partition(" ")
            idx = class_index.get(int(cid))
            if idx is not None:
                out.append(f"{idx} {rest}")
    return out


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
    class_index = yolo_class_index(project)

    for img_rec in project.images:
        split = img_rec.split or "train"
        img_path = Path(img_rec.path)
        anns = all_annotations.get(img_rec.path, [])

        labels_dir = output_dir / "labels" / split
        labels_dir.mkdir(parents=True, exist_ok=True)
        lines = yolo_label_lines(anns, ann_to_line_fn, class_index, img_rec)
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
    lines = [f"path: {output_dir.resolve().as_posix()}"]
    for s in ("train", "val", "test"):
        if s in splits:
            lines.append(f"{s}: images/{s}")
    lines.append(f"nc: {len(names)}")
    lines.append(f"names: {names}")
    (output_dir / "data.yaml").write_text("\n".join(lines), encoding="utf-8")


# ── multi-task writer ─────────────────────────────────────────────────────────

def write_yolo_multitask(project: Project,
                          all_annotations: dict,
                          output_dir: Path,
                          tasks: list,
                          copy_images: bool = True) -> None:
    """
    Write a multi-task dataset sharing a single images/ folder.

    tasks: list of (labels_dir_name, yaml_stem, ann_to_line_fn)

    Structure:
      output_dir/
        images/{split}/img.jpg          ← copied once
        labels_detect/{split}/img.txt   ← per task
        labels_segment/{split}/img.txt  ← per task
        data_detect.yaml
        data_segment.yaml
    """
    output_dir = Path(output_dir)
    class_index = yolo_class_index(project)

    for img_rec in project.images:
        split = img_rec.split or "train"
        img_path = Path(img_rec.path)
        anns = all_annotations.get(img_rec.path, [])

        for labels_dir_name, _yaml_stem, ann_fn, _yaml_extra in tasks:
            labels_dir = output_dir / labels_dir_name / split
            labels_dir.mkdir(parents=True, exist_ok=True)
            lines = yolo_label_lines(anns, ann_fn, class_index, img_rec)
            (labels_dir / (img_path.stem + ".txt")).write_text(
                "\n".join(lines), encoding="utf-8")

        if copy_images and img_path.exists():
            images_dir = output_dir / "images" / split
            images_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(img_path, images_dir / img_path.name)

    splits = sorted({r.split or "train" for r in project.images})
    names = [c.name for c in sorted(project.classes, key=lambda c: c.id)]

    for labels_dir_name, yaml_stem, _, yaml_extra in tasks:
        _write_multitask_yaml(output_dir, labels_dir_name, yaml_stem, splits, names, yaml_extra)


def _write_multitask_yaml(output_dir: Path, labels_dir_name: str,
                           yaml_stem: str, splits: list, names: list,
                           extra: str | None = None) -> None:
    lines = [
        f"# Multi-task export — images shared at images/{{split}}/",
        f"# Labels at {labels_dir_name}/{{split}}/",
        f"path: {output_dir.resolve().as_posix()}",
    ]
    for s in ("train", "val", "test"):
        if s in splits:
            lines.append(f"{s}: images/{s}")
    lines.append(f"label_dir: {labels_dir_name}")
    lines.append(f"nc: {len(names)}")
    lines.append(f"names: {names}")
    content = "\n".join(lines)
    if extra:
        content += extra
    (output_dir / f"{yaml_stem}.yaml").write_text(content, encoding="utf-8")


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
