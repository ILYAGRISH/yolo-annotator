"""
Semantic Masks exporter.

Output layout:
  output/
  ├── images/
  │   ├── train/  img001.jpg ...
  │   └── val/
  ├── masks/
  │   ├── train/  img001.png ...   ← grayscale PNG, pixel = class index (1-based)
  │   └── val/
  └── classes.txt                  ← index → class name

Pixel values:
  0           = background
  1, 2, 3 …  = class index in project.classes order

Supported annotation types (all composited onto one mask per image):
  MASK    — uses stored polygon contour
  SEGMENT — filled polygon
  BBOX    — filled rectangle
  OBB     — filled rotated rectangle (4 corners)
  POLYLINE — drawn with adaptive thickness (useful for crack annotations)
"""
from __future__ import annotations

import math
import shutil
from pathlib import Path

from PIL import Image as PilImage, ImageDraw

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.project import ImageRecord, Project
from annotator.exporters.base import BaseExporter


class SemanticMasksExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "Semantic Masks"

    @property
    def file_extension(self) -> str:
        return ".png"

    def export(self, project: Project, output_dir: Path, **kwargs):
        all_annotations: dict[str, list[Annotation]] = kwargs.get("all_annotations", {})
        copy_images: bool = kwargs.get("copy_images", True)

        # class_id → pixel value (1-based index in project.classes)
        class_pixel: dict[int, int] = {
            c.id: idx + 1 for idx, c in enumerate(project.classes)
        }

        # Write classes.txt legend
        classes_txt = output_dir / "classes.txt"
        with open(classes_txt, "w", encoding="utf-8") as f:
            f.write("# index: class_name  (pixel value = index)\n")
            f.write("0: background\n")
            for idx, c in enumerate(project.classes):
                f.write(f"{idx + 1}: {c.name}\n")

        for img_rec in project.images:
            anns = all_annotations.get(img_rec.path, [])
            split = img_rec.split or "train"

            masks_dir = output_dir / "masks" / split
            masks_dir.mkdir(parents=True, exist_ok=True)

            stem = Path(img_rec.path).stem
            mask = _render_mask(img_rec, anns, class_pixel,
                                project.project_path)
            mask.save(masks_dir / f"{stem}.png")

            if copy_images:
                img_dest_dir = output_dir / "images" / split
                img_dest_dir.mkdir(parents=True, exist_ok=True)
                src = Path(img_rec.path)
                if src.exists():
                    shutil.copy2(src, img_dest_dir / src.name)


# ── rendering ─────────────────────────────────────────────────────────────────

def _image_size(img_rec: ImageRecord) -> tuple[int, int]:
    """Return (width, height), loading from disk if not stored."""
    if img_rec.width > 0 and img_rec.height > 0:
        return img_rec.width, img_rec.height
    try:
        with PilImage.open(img_rec.path) as im:
            return im.size  # (w, h)
    except Exception:
        return 640, 480  # fallback


def _render_mask(img_rec: ImageRecord,
                 anns: list[Annotation],
                 class_pixel: dict[int, int],
                 project_path: Path | None) -> PilImage.Image:
    """Render all annotations for one image into a single grayscale mask."""
    w, h = _image_size(img_rec)
    mask = PilImage.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    # Adaptive polyline thickness for crack-style annotations
    line_width = max(3, min(w, h) // 150)

    for ann in anns:
        fill = class_pixel.get(ann.class_id, 1)
        t = ann.ann_type

        if t == AnnotationType.MASK:
            # Use the polygon contour stored alongside the mask PNG
            pts = _norm_to_px(ann.data.get("polygon", []), w, h)
            if len(pts) >= 3:
                draw.polygon(pts, fill=fill)

        elif t == AnnotationType.SEGMENT:
            pts = _norm_to_px(ann.data.get("points", []), w, h)
            if len(pts) >= 3:
                draw.polygon(pts, fill=fill)

        elif t == AnnotationType.POLYLINE:
            pts = _norm_to_px(ann.data.get("points", []), w, h)
            if len(pts) >= 2:
                draw.line(pts, fill=fill, width=line_width)

        elif t == AnnotationType.BBOX:
            d = ann.data
            x0, y0 = int(d["x"] * w), int(d["y"] * h)
            x1, y1 = int((d["x"] + d["w"]) * w), int((d["y"] + d["h"]) * h)
            draw.rectangle([x0, y0, x1, y1], fill=fill)

        elif t == AnnotationType.OBB:
            d = ann.data
            cx, cy = d["cx"] * w, d["cy"] * h
            hw, hh = d["w"] * w / 2, d["h"] * h / 2
            rad = math.radians(d.get("angle_deg", 0.0))
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            corners = [
                (int(cx + cos_a * lx - sin_a * ly),
                 int(cy + sin_a * lx + cos_a * ly))
                for lx, ly in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
            ]
            draw.polygon(corners, fill=fill)

    return mask


def _norm_to_px(points: list, w: int, h: int) -> list[tuple[int, int]]:
    return [(int(x * w), int(y * h)) for x, y in points]
