from pathlib import Path
from app.models.annotation import SegmentAnnotation


def load_labels(label_path: Path) -> list:
    annotations = []
    if not label_path.exists():
        return annotations
    with open(label_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                annotations.append(SegmentAnnotation.from_yolo_line(line))
            except (ValueError, IndexError) as e:
                print(f"Warning: skipping line {line_num} in {label_path}: {e}")
    return annotations


def save_labels(label_path: Path, annotations: list):
    label_path.parent.mkdir(parents=True, exist_ok=True)
    with open(label_path, "w", encoding="utf-8") as f:
        for ann in annotations:
            f.write(ann.to_yolo() + "\n")
