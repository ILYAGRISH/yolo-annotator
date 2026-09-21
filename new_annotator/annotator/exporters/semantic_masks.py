"""
Semantic Masks exporter.

Output layout:
  output/
  ├── images/
  │   ├── train/  img001.jpg ...
  │   └── val/
  ├── masks/
  │   ├── train/  img001.png ...
  │   └── val/
  └── classes.txt

Three mask modes (mask_mode kwarg):
  "binary"  — grayscale PNG, any annotation = 255, background = 0
  "index"   — grayscale PNG, pixel value = class index (1-based), background = 0
  "color"   — RGB PNG, each class drawn in its project color, background = black

Supported annotation types:
  MASK, SEGMENT — filled polygon
  BBOX          — filled rectangle
  OBB           — filled rotated rectangle
  POLYLINE      — drawn with adaptive thickness (for crack annotations)
"""
from __future__ import annotations

import math
import shutil
from pathlib import Path

from PIL import Image as PilImage, ImageDraw

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.project import ImageRecord, Project
from annotator.exporters.base import BaseExporter

_MASK_MODES = ("binary", "index", "color")


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


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
        mask_mode: str = kwargs.get("mask_mode", "index")

        if mask_mode not in _MASK_MODES:
            mask_mode = "index"

        # Build fill map: class_id → pixel value (int or RGB tuple)
        if mask_mode == "binary":
            pil_mode = "L"
            background = 0
            class_fill: dict[int, int | tuple] = {c.id: 255 for c in project.classes}
        elif mask_mode == "color":
            pil_mode = "RGB"
            background = (0, 0, 0)
            class_fill = {c.id: _hex_to_rgb(c.color) for c in project.classes}
        else:  # index
            pil_mode = "L"
            background = 0
            class_fill = {c.id: idx + 1 for idx, c in enumerate(project.classes)}

        # Write classes.txt legend
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "classes.txt", "w", encoding="utf-8") as f:
            if mask_mode == "binary":
                f.write("# binary mode: 0 = background, 255 = annotation\n")
                for c in project.classes:
                    f.write(f"255: {c.name}\n")
            elif mask_mode == "color":
                f.write("# color mode: RGB value per class\n")
                f.write("(0,0,0): background\n")
                for c in project.classes:
                    rgb = _hex_to_rgb(c.color)
                    f.write(f"({rgb[0]},{rgb[1]},{rgb[2]}): {c.name}\n")
            else:
                f.write("# index mode: pixel value = class index (0 = background)\n")
                f.write("0: background\n")
                for idx, c in enumerate(project.classes):
                    f.write(f"{idx + 1}: {c.name}\n")

        for img_rec in project.images:
            anns = all_annotations.get(img_rec.path, [])
            split = img_rec.split or "train"

            masks_dir = output_dir / "masks" / split
            masks_dir.mkdir(parents=True, exist_ok=True)

            stem = Path(img_rec.path).stem
            mask = _render_mask(img_rec, anns, class_fill,
                                pil_mode, background, project.project_path)
            mask.save(masks_dir / f"{stem}.png")

            if copy_images:
                img_dest_dir = output_dir / "images" / split
                img_dest_dir.mkdir(parents=True, exist_ok=True)
                src = Path(img_rec.path)
                if src.exists():
                    shutil.copy2(src, img_dest_dir / src.name)


# ── rendering ─────────────────────────────────────────────────────────────────

def _image_size(img_rec: ImageRecord) -> tuple[int, int]:
    if img_rec.width > 0 and img_rec.height > 0:
        return img_rec.width, img_rec.height
    try:
        with PilImage.open(img_rec.path) as im:
            return im.size
    except Exception:
        return 640, 480


def _render_mask(img_rec: ImageRecord,
                 anns: list[Annotation],
                 class_fill: dict,
                 pil_mode: str,
                 background,
                 project_path: Path | None) -> PilImage.Image:
    w, h = _image_size(img_rec)
    mask = PilImage.new(pil_mode, (w, h), background)
    draw = ImageDraw.Draw(mask)
    line_width = max(3, min(w, h) // 150)

    for ann in anns:
        fill = class_fill.get(ann.class_id, 255 if pil_mode == "L" else (255, 255, 255))
        t = ann.ann_type

        if t == AnnotationType.MASK:
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
