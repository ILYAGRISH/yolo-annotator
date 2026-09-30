"""
COCO Keypoints exporter.

Output layout:
  output_dir/
    annotations/
      keypoints_train.json
      keypoints_val.json
    images/
      train/
      val/

Annotation format per object:
  keypoints: [x1 y1 v1  x2 y2 v2  ...]   — in pixels; v: 0=absent, 2=visible
  num_keypoints: count of keypoints with v > 0
  bbox: [x, y, w, h] in pixels, auto-computed from visible keypoints + 5% margin

Category entries include:
  keypoints: list of point names (from class skeleton)
  skeleton:  list of [i, j] edge pairs (0-indexed)

Only keypoints classes (annotation_type == "keypoints") are exported.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.project import Project
from annotator.exporters.base import BaseExporter

_MARGIN = 0.05   # fraction of image dimension used as bbox padding


def _image_size(img_rec, img_path: Path) -> tuple[int, int]:
    if img_rec.width > 0 and img_rec.height > 0:
        return img_rec.width, img_rec.height
    try:
        from PIL import Image as PILImage
        with PILImage.open(img_path) as im:
            return im.width, im.height
    except Exception:
        return 0, 0


def _ann_to_coco_kpt(ann: Annotation, img_id: int, ann_id: int,
                      w: int, h: int, n_kp: int) -> dict | None:
    if ann.ann_type != AnnotationType.POSE:
        return None

    raw = ann.data.get("keypoints", [])
    if not raw:
        return None

    # Pad/trim to expected skeleton length
    kps = [list(k) for k in raw[:n_kp]]
    while len(kps) < n_kp:
        kps.append([0.0, 0.0, 0])

    # Build flat pixel list and collect visible positions
    flat: list[float] = []
    visible: list[tuple[float, float]] = []
    for kp in kps:
        px = round(kp[0] * w, 2)
        py = round(kp[1] * h, 2)
        v = int(kp[2])
        flat += [px, py, v]
        if v > 0:
            visible.append((px, py))

    if not visible:
        return None

    # Bbox from visible keypoints + margin
    xs = [p[0] for p in visible]
    ys = [p[1] for p in visible]
    mx, my = w * _MARGIN, h * _MARGIN
    bx = max(0.0, min(xs) - mx)
    by = max(0.0, min(ys) - my)
    bw = min(w - bx, max(xs) + mx - bx)
    bh = min(h - by, max(ys) + my - by)

    return {
        "id": ann_id,
        "image_id": img_id,
        "category_id": ann.class_id,
        "keypoints": flat,
        "num_keypoints": len(visible),
        "bbox": [round(bx, 2), round(by, 2), round(bw, 2), round(bh, 2)],
        "area": round(bw * bh, 2),
        "iscrowd": 0,
    }


class CocoKeypointsExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "COCO Keypoints"

    @property
    def file_extension(self) -> str:
        return ".json"

    def export(self, project: Project, output_dir: Path, **kwargs) -> None:
        all_annotations: dict = kwargs.get("all_annotations", {})
        copy_images: bool = kwargs.get("copy_images", True)

        output_dir = Path(output_dir)
        (output_dir / "annotations").mkdir(parents=True, exist_ok=True)

        # Build categories and keypoint-count map for keypoints classes only
        categories: list[dict] = []
        kp_counts: dict[int, int] = {}
        for cls in sorted(project.classes, key=lambda c: c.id):
            if cls.annotation_type != "keypoints":
                continue
            kp_names = [kp.name for kp in cls.skeleton] if cls.skeleton else []
            edges = [
                [i, j]
                for i, kp in enumerate(cls.skeleton)
                for j in kp.edges
                if i < j
            ]
            categories.append({
                "id": cls.id,
                "name": cls.name,
                "supercategory": "",
                "keypoints": kp_names,
                "skeleton": edges,
            })
            kp_counts[cls.id] = len(cls.skeleton)

        # Group images by split
        splits: dict[str, list] = {}
        for img_rec in project.images:
            splits.setdefault(img_rec.split or "train", []).append(img_rec)

        for split, img_records in splits.items():
            coco_images: list[dict] = []
            coco_anns: list[dict] = []
            ann_id = 0

            for img_id, img_rec in enumerate(img_records):
                img_path = Path(img_rec.path)
                iw, ih = _image_size(img_rec, img_path)
                coco_images.append({
                    "id": img_id,
                    "file_name": img_path.name,
                    "width": iw,
                    "height": ih,
                })

                for ann in all_annotations.get(img_rec.path, []):
                    n = kp_counts.get(ann.class_id, 0)
                    if n == 0:
                        continue
                    entry = _ann_to_coco_kpt(ann, img_id, ann_id, iw, ih, n)
                    if entry is not None:
                        coco_anns.append(entry)
                        ann_id += 1

                if copy_images and img_path.exists():
                    img_out = output_dir / "images" / split
                    img_out.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(img_path, img_out / img_path.name)

            coco_data = {
                "info": {"description": project.name, "version": "1.0"},
                "licenses": [],
                "categories": categories,
                "images": coco_images,
                "annotations": coco_anns,
            }
            (output_dir / "annotations" / f"keypoints_{split}.json").write_text(
                json.dumps(coco_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
