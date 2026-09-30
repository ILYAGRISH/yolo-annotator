"""CocoPanopticExporter — COCO panoptic segmentation format.

Output layout:
  <output_dir>/
    annotations/
      panoptic_<split>.json        (one per split)
      panoptic_<split>/
        <image_stem>.png           RGB, segment id = R + 256·G + 256²·B, 0 = void
    images/
      <split>/                     (if copy_images=True)

Every pixel belongs to at most one segment:
  stuff classes — ALL annotations of the class on an image form ONE segment
  thing classes — every annotation is its own segment (instance)
Stuff is painted first, things on top (later annotations win among things).
Role per class: LabelClass.is_stuff (panoptic_role auto / thing / stuff).

Rasterized types: MASK, SEMANTIC (pixel-exact from PNG), SEGMENT, POLYLINE
(adaptive thickness), BBOX, OBB. POSE / POINT / CLASSIFY are skipped; classes
of those types are not listed as categories.

Segment ids are derived from the class color (stuff: exact color when free,
things: jittered), so the PNGs are human-viewable; ids are unique per image.
"""
from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

import numpy as np
from PIL import Image as PilImage

from annotator.domain.project import Project
from annotator.exporters.base import BaseExporter
from annotator.exporters.raster import RASTER_CLASS_TYPES, bbox_xywh, rasterize


def _image_size(img_rec, img_path: Path) -> tuple[int, int]:
    if img_rec.width > 0 and img_rec.height > 0:
        return img_rec.width, img_rec.height
    try:
        with PilImage.open(img_path) as im:
            return im.width, im.height
    except Exception:
        return 0, 0


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 170, 170, 170


def rgb_to_id(r: int, g: int, b: int) -> int:
    return r + 256 * g + 256 * 256 * b


def id_to_rgb(seg: np.ndarray) -> np.ndarray:
    """(H,W) segment ids → (H,W,3) uint8 RGB."""
    seg = seg.astype(np.uint32)
    return np.stack([seg % 256, (seg // 256) % 256, (seg // 65536) % 256],
                    axis=-1).astype(np.uint8)


class _IdGenerator:
    """Unique non-zero segment ids near each class color."""

    def __init__(self, seed: int):
        self._used: set[int] = {0}
        self._rng = random.Random(seed)

    def next(self, rgb: tuple[int, int, int], exact: bool) -> int:
        if exact:
            sid = rgb_to_id(*rgb)
            if sid not in self._used:
                self._used.add(sid)
                return sid
        while True:
            r, g, b = (min(255, max(0, c + self._rng.randint(-40, 40))) for c in rgb)
            sid = rgb_to_id(r, g, b)
            if sid not in self._used:
                self._used.add(sid)
                return sid


def render_panoptic(anns: list, w: int, h: int, project: Project,
                    seed: int = 0) -> tuple[np.ndarray, list[dict]]:
    """
    Build the panoptic id map for one image.
    Returns ((H,W) uint32 segment ids, segments_info list).
    """
    seg = np.zeros((h, w), dtype=np.uint32)
    ids = _IdGenerator(seed)
    seg_class: dict[int, int] = {}        # segment id → class id

    stuff: dict[int, np.ndarray] = {}     # class id → merged mask (insertion order)
    things: list[tuple[int, np.ndarray]] = []
    for ann in anns:
        cls = project.get_class(ann.class_id)
        if cls is None or cls.annotation_type not in RASTER_CLASS_TYPES:
            continue
        mask = rasterize(ann, w, h, project.project_path)
        if mask is None or not mask.any():
            continue
        if cls.is_stuff:
            prev = stuff.get(cls.id)
            stuff[cls.id] = mask if prev is None else (prev | mask)
        else:
            things.append((cls.id, mask))

    for cid, mask in stuff.items():
        sid = ids.next(_hex_to_rgb(project.get_class(cid).color), exact=True)
        seg[mask] = sid
        seg_class[sid] = cid
    for cid, mask in things:
        sid = ids.next(_hex_to_rgb(project.get_class(cid).color), exact=False)
        seg[mask] = sid
        seg_class[sid] = cid

    segments: list[dict] = []
    for sid, cid in seg_class.items():
        visible = seg == sid
        area = int(visible.sum())
        if area == 0:                    # fully covered by later segments
            continue
        segments.append({
            "id": int(sid),
            "category_id": cid,
            "area": area,
            "bbox": bbox_xywh(visible),
            "iscrowd": 0,
        })
    return seg, segments


class CocoPanopticExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "COCO Panoptic"

    @property
    def file_extension(self) -> str:
        return ".json"

    def export(self, project: Project, output_dir: Path, **kwargs) -> None:
        all_annotations: dict = kwargs.get("all_annotations", {})
        copy_images: bool = kwargs.get("copy_images", True)

        output_dir = Path(output_dir)
        ann_dir = output_dir / "annotations"
        ann_dir.mkdir(parents=True, exist_ok=True)

        categories = [
            {"id": c.id, "name": c.name, "supercategory": "",
             "isthing": 0 if c.is_stuff else 1,
             "color": list(_hex_to_rgb(c.color))}
            for c in sorted(project.classes, key=lambda c: c.id)
            if c.annotation_type in RASTER_CLASS_TYPES
        ]

        splits: dict[str, list] = {}
        for img_rec in project.images:
            splits.setdefault(img_rec.split or "train", []).append(img_rec)

        for split, img_records in splits.items():
            png_dir = ann_dir / f"panoptic_{split}"
            png_dir.mkdir(parents=True, exist_ok=True)
            coco_images: list[dict] = []
            coco_anns: list[dict] = []

            for img_id, img_rec in enumerate(img_records):
                img_path = Path(img_rec.path)
                iw, ih = _image_size(img_rec, img_path)
                if iw <= 0 or ih <= 0:
                    continue
                coco_images.append({"id": img_id, "file_name": img_path.name,
                                    "width": iw, "height": ih})

                seg, segments = render_panoptic(
                    all_annotations.get(img_rec.path, []), iw, ih, project,
                    seed=img_id)
                png_name = f"{img_path.stem}.png"
                PilImage.fromarray(id_to_rgb(seg), mode="RGB").save(png_dir / png_name)
                coco_anns.append({"image_id": img_id, "file_name": png_name,
                                  "segments_info": segments})

                if copy_images and img_path.exists():
                    img_out = output_dir / "images" / split
                    img_out.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(img_path, img_out / img_path.name)

            (ann_dir / f"panoptic_{split}.json").write_text(
                json.dumps({
                    "info": {"description": project.name, "version": "1.0"},
                    "licenses": [],
                    "categories": categories,
                    "images": coco_images,
                    "annotations": coco_anns,
                }, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
