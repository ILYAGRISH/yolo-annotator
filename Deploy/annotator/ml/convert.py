"""
Model output (yolo.predict, pixels) -> project Annotations (normalised).

The TARGET CLASS decides the geometry: a detection mapped onto a `bbox`
class becomes a box, onto a `polygon` class a polygon, onto a `mask` class a
brush-style PNG mask, and so on. Pure functions apart from writing mask PNGs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.label_class import LabelClass

# class.annotation_type -> AnnotationType
ANN_TYPE = {
    "bbox": AnnotationType.BBOX,
    "polygon": AnnotationType.SEGMENT,
    "obb": AnnotationType.OBB,
    "keypoints": AnnotationType.POSE,
    "point": AnnotationType.POINT,
    "mask": AnnotationType.MASK,
    "classification": AnnotationType.CLASSIFY,
}

# model task -> class types its output can fill (first = the natural one)
COMPATIBLE = {
    "detect":   ["bbox", "obb", "polygon", "mask", "point"],
    "segment":  ["polygon", "mask", "bbox", "obb", "point"],
    "obb":      ["obb", "bbox", "polygon", "point"],
    "pose":     ["keypoints", "bbox", "point"],
    "classify": ["classification"],
}

SOURCE_MODEL = "model"           # Annotation.meta["source"] of pre-labelled annotations


def default_class_type(task: str) -> str:
    return COMPATIBLE.get(task, ["bbox"])[0]


def compatible(task: str, class_type: str) -> bool:
    return class_type in COMPATIBLE.get(task, [])


def is_model_annotation(ann: Annotation) -> bool:
    return ann.meta.get("source") == SOURCE_MODEL


@dataclass
class ConvertOptions:
    model_name: str = ""
    simplify_px: float = 2.0         # polygon classes: Douglas-Peucker tolerance
    kpt_threshold: float = 0.5       # keypoint confidence -> visible (2) / not labelled (0)
    min_conf: float = 0.0            # classify: the top-1 class must reach it (detections are
                                     # already filtered by the model's own conf threshold)
    project_path: Path | None = None  # needed for `mask` classes (PNG files)
    image_stem: str = ""
    tool: str = "yolo"               # Annotation.meta["tool"]
    source: str = SOURCE_MODEL       # "manual" for interactive tools (SAM): no 🤖, no confidence


@dataclass
class ConvertReport:
    added: int = 0
    skipped: dict[str, int] = field(default_factory=dict)

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1


def convert(result: dict, mapping: dict[int, LabelClass | None],
            opts: ConvertOptions, existing: list[Annotation] = (),
            report: ConvertReport | None = None) -> list[Annotation]:
    """yolo.predict result -> new Annotations. Unmapped / incompatible
    detections are skipped (and counted in `report`)."""
    report = report if report is not None else ConvertReport()
    W, H = int(result["width"]), int(result["height"])
    task = result.get("task", "detect")
    out: list[Annotation] = []

    if result.get("classification"):
        best = result["classification"][0]
        lc = mapping.get(int(best["cls"]))
        if lc is None:
            report.skip("class not mapped")
        elif best["conf"] < opts.min_conf:
            report.skip("below confidence")
        elif lc.annotation_type != "classification":
            report.skip("incompatible class type")
        elif any(a.ann_type == AnnotationType.CLASSIFY and a.class_id == lc.id for a in existing):
            report.skip("already labelled")
        else:
            out.append(_new(lc, AnnotationType.CLASSIFY, {}, best["conf"], opts))
        report.added += len(out)
        return out

    for det in result.get("detections", []):
        lc = mapping.get(int(det["cls"]))
        if lc is None:
            report.skip("class not mapped")
            continue
        if not compatible(task, lc.annotation_type):
            report.skip("incompatible class type")
            continue
        ann = _one(det, lc, W, H, opts, report)
        if ann is not None:
            out.append(ann)
    report.added += len(out)
    return out


# ── geometry ──────────────────────────────────────────────────────────────────

def _one(det: dict, lc: LabelClass, W: int, H: int,
         opts: ConvertOptions, report: ConvertReport) -> Annotation | None:
    kind, conf = lc.annotation_type, det["conf"]

    if kind == "bbox":
        x1, y1, x2, y2 = _clamp_box(det["box"], W, H)
        if x2 - x1 < 1 or y2 - y1 < 1:
            report.skip("empty geometry")
            return None
        return _new(lc, AnnotationType.BBOX,
                    {"x": x1 / W, "y": y1 / H, "w": (x2 - x1) / W, "h": (y2 - y1) / H}, conf, opts)

    if kind == "obb":
        if det.get("obb"):
            cx, cy, w, h, r = det["obb"]
            angle = math.degrees(r)
        else:
            x1, y1, x2, y2 = _clamp_box(det["box"], W, H)
            cx, cy, w, h, angle = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1, 0.0
        if w < 1 or h < 1:
            report.skip("empty geometry")
            return None
        return _new(lc, AnnotationType.OBB,
                    {"cx": cx / W, "cy": cy / H, "w": w / W, "h": h / H, "angle_deg": angle}, conf, opts)

    if kind == "point":
        x1, y1, x2, y2 = _clamp_box(det["box"], W, H)
        return _new(lc, AnnotationType.POINT,
                    {"x": (x1 + x2) / 2 / W, "y": (y1 + y2) / 2 / H}, conf, opts)

    if kind == "polygon":
        polys = _pixel_polygons(det, W, H)
        poly = _simplify(polys[0], opts.simplify_px) if polys else []
        if len(poly) < 3:
            report.skip("empty geometry")
            return None
        return _new(lc, AnnotationType.SEGMENT,
                    {"points": [[x / W, y / H] for x, y in poly]}, conf, opts)

    if kind == "mask":
        return _mask(det, lc, W, H, opts, report)

    if kind == "keypoints":
        kps = det.get("keypoints") or []
        if not lc.skeleton or len(kps) != len(lc.skeleton):
            report.skip("keypoint count differs from the class skeleton")
            return None
        points = []
        for x, y, c in kps:
            if c >= opts.kpt_threshold and 0 <= x <= W and 0 <= y <= H:
                points.append([x / W, y / H, 2])
            else:
                points.append([0.0, 0.0, 0])
        if not any(v for _, _, v in points):
            report.skip("no visible keypoints")
            return None
        return _new(lc, AnnotationType.POSE, {"keypoints": points}, conf, opts)

    report.skip("incompatible class type")
    return None


def _mask(det, lc, W, H, opts, report):
    import cv2
    import numpy as np
    from annotator.storage.mask_storage import MaskStorage

    if opts.project_path is None:
        report.skip("no project folder for masks")
        return None
    polys = _pixel_polygons(det, W, H)
    bitmap = np.zeros((H, W), dtype=np.uint8)
    pts = [np.round(np.asarray(p, dtype=np.float64)).astype(np.int32) for p in polys if len(p) >= 3]
    if pts:
        cv2.fillPoly(bitmap, pts, 255)
    if not bitmap.any():
        report.skip("empty geometry")
        return None
    storage = MaskStorage(opts.project_path)
    ann = _new(lc, AnnotationType.MASK, {}, det["conf"], opts)
    ann.data = {"mask_png_path": storage.save_mask(ann.id, opts.image_stem, bitmap),
                "polygon": storage.mask_to_polygon(bitmap, W, H),
                "bbox": storage.mask_to_bbox(bitmap, W, H)}
    return ann


def _pixel_polygons(det: dict, W: int, H: int) -> list[list[list[float]]]:
    """Outlines in pixels: the mask parts (segment), else the (rotated) box."""
    if det.get("polygons"):
        return [[[_clip(x, W), _clip(y, H)] for x, y in p] for p in det["polygons"]]
    if det.get("obb"):
        cx, cy, w, h, r = det["obb"]
        c, s = math.cos(r), math.sin(r)
        corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
        return [[[_clip(cx + c * dx - s * dy, W), _clip(cy + s * dx + c * dy, H)]
                 for dx, dy in corners]]
    x1, y1, x2, y2 = _clamp_box(det["box"], W, H)
    return [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]]


def min_area_rect(poly) -> list[float]:
    """Tightest rotated box around an outline: [cx, cy, w, h, angle_rad]
    (pixels, y down — the convention of yolo.predict's "obb")."""
    import cv2
    import numpy as np
    (cx, cy), (w, h), angle = cv2.minAreaRect(np.asarray(poly, dtype=np.float32))
    return [float(cx), float(cy), float(w), float(h), math.radians(angle)]


def _simplify(poly: list[list[float]], tol: float) -> list[list[float]]:
    if tol <= 0 or len(poly) <= 4:
        return poly
    from shapely.geometry import Polygon
    try:
        simple = Polygon(poly).simplify(tol, preserve_topology=True)
        coords = list(simple.exterior.coords)[:-1] if not simple.is_empty else []
    except Exception:                       # noqa: BLE001 — invalid ring: keep the original
        return poly
    return [[float(x), float(y)] for x, y in coords] if len(coords) >= 3 else poly


def _clip(v: float, hi: int) -> float:
    return min(max(float(v), 0.0), float(hi))


def _clamp_box(box, W, H):
    x1, y1, x2, y2 = box
    return _clip(x1, W), _clip(y1, H), _clip(x2, W), _clip(y2, H)


def _new(lc: LabelClass, ann_type: AnnotationType, data: dict, conf: float,
         opts: ConvertOptions) -> Annotation:
    ann = Annotation.new(lc.id, ann_type, data, tool=opts.tool)
    ann.meta["source"] = opts.source
    if opts.source == SOURCE_MODEL:
        ann.meta["confidence"] = round(float(conf), 3)
    if opts.model_name:
        ann.meta["model"] = opts.model_name
    return ann
