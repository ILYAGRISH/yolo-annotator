"""
MOTChallenge exporter (Phase 8-B) — object tracks of imported videos.

One sequence per video:

    <out>/<video_id>/
        img1/000001.jpg …        extracted frames, renumbered 1..N (copy_images)
        gt/gt.txt                frame,id,left,top,width,height,conf,class,visibility
        seqinfo.ini              name, frameRate, seqLength, imWidth, imHeight
        frames.csv               index,video_frame,image  (back to the source video)
    <out>/classes.txt            class number (as in gt.txt) and name

Only annotations that belong to a track (meta.track_id) are written; the box
is the axis-aligned box of any geometry (OBB, polygon, keypoints…) in pixels.
`frame` counts the extracted frames (1-based); frameRate = video fps / step.
`class` = YOLO class index + 1 (MOT classes start at 1).
"""
from __future__ import annotations

import math
import shutil
from pathlib import Path

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.tracks import track_id
from annotator.exporters.base import BaseExporter, image_size, yolo_class_index


def pixel_box(ann: Annotation, w: int, h: int) -> tuple[float, float, float, float] | None:
    """(left, top, width, height) in pixels, or None (points, broken data)."""
    d, t = ann.data, ann.ann_type
    try:
        if t == AnnotationType.BBOX:
            return d["x"] * w, d["y"] * h, d["w"] * w, d["h"] * h
        if t == AnnotationType.OBB:
            cx, cy, bw, bh = d["cx"] * w, d["cy"] * h, d["w"] * w, d["h"] * h
            a = math.radians(d.get("angle_deg", 0.0))
            ca, sa = math.cos(a), math.sin(a)
            xs = [cx + dx * ca - dy * sa for dx, dy in
                  ((-bw / 2, -bh / 2), (bw / 2, -bh / 2), (bw / 2, bh / 2), (-bw / 2, bh / 2))]
            ys = [cy + dx * sa + dy * ca for dx, dy in
                  ((-bw / 2, -bh / 2), (bw / 2, -bh / 2), (bw / 2, bh / 2), (-bw / 2, bh / 2))]
            return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
        if t in (AnnotationType.SEGMENT, AnnotationType.POLYLINE):
            pts = d["points"]
        elif t == AnnotationType.POSE:
            pts = [(x, y) for x, y, v in d["keypoints"] if v > 0]
        elif t == AnnotationType.MASK:
            cx, cy, bw, bh = d["bbox"]
            return (cx - bw / 2) * w, (cy - bh / 2) * h, bw * w, bh * h
        else:
            return None
        if not pts:
            return None
        xs, ys = [p[0] * w for p in pts], [p[1] * h for p in pts]
        return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    except (KeyError, TypeError, ValueError):
        return None


class MotExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "MOTChallenge"

    @property
    def file_extension(self) -> str:
        return ".txt"

    def export(self, project, output_dir: Path, **kwargs):
        output_dir = Path(output_dir)
        all_anns = kwargs.get("all_annotations", {})
        copy_images = kwargs.get("copy_images", True)
        cls_index = yolo_class_index(project)
        self.boxes = 0
        output_dir.mkdir(parents=True, exist_ok=True)
        names = sorted(project.classes, key=lambda c: c.id)
        (output_dir / "classes.txt").write_text(
            "".join(f"{i + 1} {c.name}\n" for i, c in enumerate(names)), encoding="utf-8")

        for vid, info in project.videos.items():
            recs = sorted((r for r in project.images if r.video == vid), key=lambda r: r.frame)
            if not recs:
                continue
            seq = output_dir / vid
            (seq / "gt").mkdir(parents=True, exist_ok=True)
            lines, rows = [], ["index,video_frame,image"]
            w = h = 0
            for idx, rec in enumerate(recs, start=1):
                w, h = image_size(rec)
                rows.append(f"{idx},{rec.frame},{Path(rec.path).name}")
                if copy_images and Path(rec.path).exists():
                    (seq / "img1").mkdir(exist_ok=True)
                    shutil.copy2(rec.path, seq / "img1" / f"{idx:06d}{Path(rec.path).suffix}")
                for ann in all_anns.get(rec.path, []):
                    tid = track_id(ann)
                    box = pixel_box(ann, w, h) if tid is not None else None
                    if box is None or ann.class_id not in cls_index:
                        continue
                    left, top, bw, bh = box
                    lines.append((idx, tid, f"{idx},{tid},{left:.2f},{top:.2f},{bw:.2f},{bh:.2f},"
                                            f"1,{cls_index[ann.class_id] + 1},1"))
            lines.sort(key=lambda x: (x[0], x[1]))
            self.boxes += len(lines)
            (seq / "gt" / "gt.txt").write_text("".join(l + "\n" for _, _, l in lines),
                                               encoding="utf-8")
            (seq / "frames.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
            step = info.get("step", 1) or 1
            rate = round((info.get("fps") or 25.0) / step, 3)
            ext = Path(recs[0].path).suffix
            (seq / "seqinfo.ini").write_text(
                "[Sequence]\n"
                f"name={vid}\nimDir=img1\nframeRate={rate:g}\nseqLength={len(recs)}\n"
                f"imWidth={w}\nimHeight={h}\nimExt={ext}\n", encoding="utf-8")
