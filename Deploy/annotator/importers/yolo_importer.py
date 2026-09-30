"""
YOLO dataset importer.

Reads YOLO-format label files and converts them to internal Annotation objects.
Supports: Detect, OBB, Segment, Point, Classify.

Dataset layouts handled:
  dataset/
  ├── data.yaml  or  classes.txt
  ├── images/
  │   ├── train/  (optional split subdirs)
  │   └── val/
  └── labels/
      ├── train/
      └── val/

Class resolution:
  - Matches YOLO class names to existing project classes by name (case-insensitive).
  - Creates new classes for any unmatched names.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from annotator.domain.annotation import Annotation, AnnotationType

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

# ann_type key → (AnnotationType for annotations, annotation_type for LabelClass)
_ANN_MAP: dict[str, tuple[AnnotationType, str]] = {
    "detect":   (AnnotationType.BBOX,     "bbox"),
    "obb":      (AnnotationType.OBB,      "obb"),
    "segment":  (AnnotationType.SEGMENT,  "polygon"),
    "point":    (AnnotationType.POINT,    "point"),
    "classify": (AnnotationType.CLASSIFY, "classification"),
}


@dataclass
class ImportResult:
    images_found: int = 0
    labels_found: int = 0
    annotations_added: int = 0
    images_skipped: int = 0
    classes_created: int = 0
    warnings: list[str] = field(default_factory=list)


# ── class file parsers ────────────────────────────────────────────────────────

def _parse_yaml_names(text: str) -> list[str]:
    """Minimal parser for the 'names' field in data.yaml (no PyYAML required)."""
    lines = text.splitlines()
    in_names = False
    names: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("names:"):
            rest = stripped[6:].strip()
            if rest.startswith("["):
                # names: ['car', 'person', 'truck']
                rest = rest.strip("[]")
                parts = [p.strip().strip("'\"") for p in rest.split(",")]
                return [p for p in parts if p]
            elif rest:
                return [rest.strip("'\"")]
            else:
                in_names = True
        elif in_names:
            if stripped.startswith("- "):
                names.append(stripped[2:].strip().strip("'\""))
            elif re.match(r"^\d+:", stripped):
                val = stripped.split(":", 1)[1].strip().strip("'\"")
                names.append(val)
            elif stripped and not stripped.startswith("#"):
                if not (stripped.startswith("-") or re.match(r"^\d+:", stripped)):
                    break

    return names


def parse_class_names(class_file: Path) -> list[str]:
    """Read class names from data.yaml or classes.txt."""
    text = class_file.read_text(encoding="utf-8")
    if class_file.suffix.lower() in (".yaml", ".yml"):
        return _parse_yaml_names(text)
    # classes.txt: one class per line
    return [line.strip() for line in text.splitlines() if line.strip()]


def auto_find_class_file(dataset_root: Path) -> Path | None:
    """Return the first data.yaml or classes.txt found in dataset_root."""
    for name in ("data.yaml", "data.yml", "classes.txt", "obj.names"):
        p = dataset_root / name
        if p.exists():
            return p
    return None


# ── image/label file discovery ────────────────────────────────────────────────

def find_images_with_split(dataset_root: Path) -> list[tuple[Path, str]]:
    """
    Return [(image_path, split_name), ...] for all images in the dataset.
    Respects train/val/test subdirectory layout when present.
    """
    results: list[tuple[Path, str]] = []

    # Prefer images/ subfolder, else search from root
    search_root = dataset_root
    for candidate in ("images", "img", "imgs", "JPEGImages"):
        d = dataset_root / candidate
        if d.is_dir():
            search_root = d
            break

    split_dirs_found = [
        s for s in ("train", "val", "test") if (search_root / s).is_dir()
    ]

    if split_dirs_found:
        for split in ("train", "val", "test"):
            split_dir = search_root / split
            if not split_dir.is_dir():
                continue
            for ext in IMAGE_EXTS:
                for p in split_dir.glob(f"*{ext}"):
                    results.append((p, split))
                for p in split_dir.glob(f"*{ext.upper()}"):
                    results.append((p, split))
    else:
        for ext in IMAGE_EXTS:
            for p in search_root.glob(f"*{ext}"):
                results.append((p, "train"))
            for p in search_root.glob(f"*{ext.upper()}"):
                results.append((p, "train"))

    # Deduplicate (case sensitivity on Windows)
    seen: set[str] = set()
    unique = []
    for p, s in results:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            unique.append((p, s))
    return unique


def find_label_file(image_path: Path, dataset_root: Path) -> Path | None:
    """Find the YOLO .txt label file corresponding to an image."""
    stem = image_path.stem

    # Strategy 1: replace 'images' directory component with 'labels'
    try:
        rel = image_path.relative_to(dataset_root)
        parts = list(rel.parts)
        for i, part in enumerate(parts):
            if part.lower() in ("images", "img", "imgs", "jpegimages"):
                new_parts = parts[:i] + ["labels"] + parts[i + 1:]
                new_parts[-1] = stem + ".txt"
                candidate = dataset_root.joinpath(*new_parts)
                if candidate.exists():
                    return candidate
    except ValueError:
        pass

    # Strategy 2: sibling labels/<split>/ folder
    candidate = image_path.parent.parent / "labels" / image_path.parent.name / f"{stem}.txt"
    if candidate.exists():
        return candidate

    # Strategy 3: labels/ at dataset root level matching split
    candidate = dataset_root / "labels" / image_path.parent.name / f"{stem}.txt"
    if candidate.exists():
        return candidate

    # Strategy 4: labels/ in same directory as image
    candidate = image_path.parent / "labels" / f"{stem}.txt"
    if candidate.exists():
        return candidate

    # Strategy 5: same directory as image
    candidate = image_path.parent / f"{stem}.txt"
    if candidate.exists():
        return candidate

    return None


# ── per-line parsers ──────────────────────────────────────────────────────────

def _parse_detect(parts: list[float]) -> dict:
    cx, cy, w, h = parts[1], parts[2], parts[3], parts[4]
    return {"x": cx - w / 2, "y": cy - h / 2, "w": w, "h": h}


def _parse_obb(parts: list[float]) -> dict:
    # x1 y1 x2 y2 x3 y3 x4 y4  (TL→TR→BR→BL, normalized)
    coords = parts[1:]
    p = [(coords[i], coords[i + 1]) for i in range(0, 8, 2)]
    cx = sum(x for x, _ in p) / 4
    cy = sum(y for _, y in p) / 4
    # top edge: TL→TR
    dx, dy = p[1][0] - p[0][0], p[1][1] - p[0][1]
    w = math.sqrt(dx * dx + dy * dy)
    # left edge: TL→BL
    dx2, dy2 = p[3][0] - p[0][0], p[3][1] - p[0][1]
    h = math.sqrt(dx2 * dx2 + dy2 * dy2)
    angle_deg = math.degrees(math.atan2(dy, dx))
    return {"cx": cx, "cy": cy, "w": w, "h": h, "angle_deg": angle_deg}


def _parse_segment(parts: list[float]) -> dict:
    coords = parts[1:]
    pts = [[coords[i], coords[i + 1]] for i in range(0, len(coords) - 1, 2)]
    return {"points": pts}


def _parse_point(parts: list[float]) -> dict:
    # 1-keypoint pose: class cx cy w h x y v
    if len(parts) >= 8:
        return {"x": parts[5], "y": parts[6]}
    # fallback: bbox center
    return {"x": parts[1], "y": parts[2]}


_PARSERS: dict[str, tuple] = {
    "detect":  (_parse_detect,  AnnotationType.BBOX),
    "obb":     (_parse_obb,     AnnotationType.OBB),
    "segment": (_parse_segment, AnnotationType.SEGMENT),
    "point":   (_parse_point,   AnnotationType.POINT),
}


def parse_label_file(label_path: Path, ann_type: str,
                     class_id_map: dict[int, int]) -> list[Annotation]:
    """Parse one YOLO .txt label file into Annotation objects."""
    parser_fn, ann_enum = _PARSERS[ann_type]
    annotations: list[Annotation] = []

    for line in label_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parts = [float(v) for v in line.split()]
            if len(parts) < 2:
                continue
            src_id = int(parts[0])
            proj_id = class_id_map.get(src_id)
            if proj_id is None:
                continue
            data = parser_fn(parts)
            ann = Annotation.new(proj_id, ann_enum, data, tool="imported")
            annotations.append(ann)
        except (ValueError, IndexError):
            continue

    return annotations


# ── main importer ─────────────────────────────────────────────────────────────

class YoloImporter:

    # ── public methods ────────────────────────────────────────────────────────

    def import_detect(self, project, dataset_root: Path, class_names: list[str],
                      ann_type: str, conflict_mode: str) -> ImportResult:
        """
        Import a YOLO Detect / OBB / Segment / Point dataset.

        conflict_mode: "skip" | "replace" | "merge"
        ann_type:      "detect" | "obb" | "segment" | "point"
        """
        from annotator.storage.project_store import ProjectStore

        result = ImportResult()
        class_id_map, result.classes_created = self._resolve_classes(
            project, class_names, _ANN_MAP[ann_type][1])

        image_files = find_images_with_split(dataset_root)
        result.images_found = len(image_files)

        existing_with_anns = self._images_with_annotations(project)

        for img_path, split in image_files:
            label_path = find_label_file(img_path, dataset_root)
            if label_path is None:
                continue

            result.labels_found += 1
            stem = img_path.stem

            if stem in existing_with_anns and conflict_mode == "skip":
                result.images_skipped += 1
                continue

            anns = parse_label_file(label_path, ann_type, class_id_map)
            if not anns:
                continue

            img_proj_path = self._ensure_image(project, img_path, split)
            if img_proj_path is None:
                result.warnings.append(f"Could not register image: {img_path.name}")
                continue

            if conflict_mode == "merge":
                existing = ProjectStore.load_annotations(project, img_proj_path)
                anns = existing + anns

            ProjectStore.save_annotations(project, img_proj_path, anns)
            result.annotations_added += len(anns)

        return result

    def import_classify(self, project, dataset_root: Path, class_names: list[str],
                        conflict_mode: str) -> ImportResult:
        """Import a YOLO Classify dataset (split/<class_name>/image.jpg)."""
        from annotator.storage.project_store import ProjectStore

        result = ImportResult()
        _, class_ann_type = _ANN_MAP["classify"]

        # Ensure all named classes exist in project
        class_id_map, result.classes_created = self._resolve_classes(
            project, class_names, class_ann_type)
        # Also build a name→id map for folder-name matching
        name_to_id = {c.name.lower(): c.id for c in project.classes}

        existing_with_anns = self._images_with_annotations(project)

        split_dirs: list[tuple[str, Path]] = []
        for s in ("train", "val", "test"):
            d = dataset_root / s
            if d.is_dir():
                split_dirs.append((s, d))
        if not split_dirs:
            split_dirs = [("train", dataset_root)]

        for split_name, split_dir in split_dirs:
            for class_dir in sorted(split_dir.iterdir()):
                if not class_dir.is_dir():
                    continue
                proj_id = name_to_id.get(class_dir.name.lower())
                if proj_id is None:
                    result.warnings.append(
                        f"Class '{class_dir.name}' not in class list — skipped")
                    continue

                for img_path in sorted(class_dir.iterdir()):
                    if img_path.suffix.lower() not in IMAGE_EXTS:
                        continue
                    result.images_found += 1

                    if img_path.stem in existing_with_anns and conflict_mode == "skip":
                        result.images_skipped += 1
                        continue

                    img_proj_path = self._ensure_image(project, img_path, split_name)
                    if img_proj_path is None:
                        continue

                    ann = Annotation.new(proj_id, AnnotationType.CLASSIFY, {},
                                        tool="imported")

                    if conflict_mode == "merge":
                        existing = ProjectStore.load_annotations(project, img_proj_path)
                        all_anns = existing + [ann]
                    else:
                        all_anns = [ann]

                    ProjectStore.save_annotations(project, img_proj_path, all_anns)
                    result.annotations_added += 1

        return result

    # ── helpers ───────────────────────────────────────────────────────────────

    def _resolve_classes(self, project, class_names: list[str],
                         ann_type: str) -> tuple[dict[int, int], int]:
        """Map YOLO class indices to project class IDs, creating new classes as needed."""
        existing_by_name = {c.name.lower(): c for c in project.classes}
        class_id_map: dict[int, int] = {}
        created = 0

        for i, name in enumerate(class_names):
            existing = existing_by_name.get(name.lower())
            if existing:
                class_id_map[i] = existing.id
            else:
                lc = project.add_class(name)
                lc.annotation_type = ann_type
                existing_by_name[name.lower()] = lc
                class_id_map[i] = lc.id
                created += 1

        return class_id_map, created

    def _images_with_annotations(self, project) -> set[str]:
        """Return stems of images that already have annotation files."""
        if not project.project_path:
            return set()
        ann_dir = project.project_path / "annotations"
        if not ann_dir.exists():
            return set()
        stems = set()
        for f in ann_dir.glob("*.json"):
            if f.stat().st_size > 5:  # non-empty
                stems.add(f.stem)
        return stems

    def _ensure_image(self, project, img_path: Path, split: str) -> str | None:
        """Register image in project if not already present. Returns project image path."""
        from PyQt6.QtGui import QImageReader
        stem = img_path.stem

        existing = next((r for r in project.images
                         if Path(r.path).stem == stem), None)
        if existing:
            return existing.path

        reader = QImageReader(str(img_path))
        sz = reader.size()
        w, h = (sz.width(), sz.height()) if sz.isValid() else (0, 0)
        rec = project.add_image(str(img_path), width=w, height=h)
        rec.split = split
        return str(img_path)
