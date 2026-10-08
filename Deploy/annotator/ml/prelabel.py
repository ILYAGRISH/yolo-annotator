"""
Pre-labelling engine: images -> yolo.predict -> project annotations.

One request per image, sent only after the previous reply: cancel is instant,
results are written as they arrive (a cancelled run keeps what it did), and a
bad image only skips that image. A backend that is gone stops the run.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from annotator.domain.label_class import LabelClass, SkeletonKeypoint
from annotator.domain.project import DEFAULT_CLASS_NAME
from annotator.ml.client import (BACKEND_EXITED, NOT_CONFIGURED, START_FAILED,
                                 STOPPED_ERR, MLBackend, Reply)
from annotator.ml.convert import (ConvertOptions, ConvertReport, convert, min_area_rect,
                                  is_model_annotation)
from annotator.ml.prelabel_settings import (EXISTING_REPLACE, EXISTING_SKIP,
                                            PrelabelSettings)
from ml_backend import protocol

# detector boxes going into these class types are outlined by SAM (sam_refine)
SAM_REFINED_TYPES = ("polygon", "mask", "obb")

# a reply of this type ends the whole run, not just one image
_FATAL = {BACKEND_EXITED, NOT_CONFIGURED, START_FAILED, STOPPED_ERR,
          protocol.MISSING_PACKAGE, protocol.CANCELLED}

COCO_KEYPOINTS = ["nose", "left_eye", "right_eye", "left_ear", "right_ear",
                  "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
                  "left_wrist", "right_wrist", "left_hip", "right_hip",
                  "left_knee", "right_knee", "left_ankle", "right_ankle"]
COCO_SKELETON = [(15, 13), (13, 11), (16, 14), (14, 12), (11, 12), (5, 11), (6, 12),
                 (5, 6), (5, 7), (6, 8), (7, 9), (8, 10), (1, 2), (0, 1), (0, 2),
                 (1, 3), (2, 4), (3, 5), (4, 6)]


@dataclass
class PrelabelSummary:
    total: int = 0
    processed: int = 0
    skipped_existing: int = 0
    failed: int = 0
    added: int = 0
    replaced: int = 0
    skip_reasons: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)     # first few "image: message"
    cancelled: bool = False
    fatal: str = ""
    seconds: float = 0.0
    changed_images: set = field(default_factory=set)
    sam_outlined: int = 0                       # detector boxes turned into SAM outlines


def make_skeleton(n_kpts: int) -> list[SkeletonKeypoint]:
    """Skeleton for a class created from a pose model: COCO names + edges for
    17 points, plain kp0..kpN otherwise."""
    if n_kpts == len(COCO_KEYPOINTS):
        edges: dict[int, list[int]] = {i: [] for i in range(n_kpts)}
        for a, b in COCO_SKELETON:
            edges[a].append(b)
            edges[b].append(a)
        return [SkeletonKeypoint(COCO_KEYPOINTS[i], sorted(edges[i])) for i in range(n_kpts)]
    return [SkeletonKeypoint(f"kp{i}") for i in range(n_kpts)]


def unused_placeholder(ctrl, keep_ids=()) -> LabelClass | None:
    """The default class of a new project ("object") when it is still the only
    class, has no annotations and is not in `keep_ids` — classes created from a
    model replace it (a project can't be left with no classes otherwise)."""
    classes = ctrl.project.classes
    if len(classes) != 1:
        return None
    c = classes[0]
    if c.name != DEFAULT_CLASS_NAME or c.id in keep_ids or ctrl.count_annotations_for_class(c.id):
        return None
    return c


def create_classes(ctrl, specs: list[tuple[str, str]], kpt_count: int | None = None,
                   replace: LabelClass | None = None) -> list[LabelClass]:
    """Add classes [(name, annotation_type)] to the project in ONE save /
    project_changed (a COCO model has 80 classes). `replace` (see
    unused_placeholder) is removed first, so the new ids start from 0."""
    project = ctrl.project
    if replace is not None and specs:
        project.remove_class(replace.id)
    created = []
    for name, ann_type in specs:
        lc = project.add_class(name)
        lc.annotation_type = ann_type
        if ann_type == "keypoints" and kpt_count:
            lc.skeleton = make_skeleton(kpt_count)
        created.append(lc)
    if created:
        ctrl.save_project()
        ctrl.project_changed.emit(project)
    return created


class PrelabelRunner(QObject):
    progress = pyqtSignal(int, int, str)       # done, total, current image name
    finished = pyqtSignal(object)              # PrelabelSummary

    def __init__(self, backend: MLBackend, ctrl, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._ctrl = ctrl
        self._images: list[str] = []
        self._idx = 0
        self._rid: int | None = None
        self._cancel = False
        self._running = False
        self._t0 = 0.0
        self.summary = PrelabelSummary()

    @property
    def running(self) -> bool:
        return self._running

    def start(self, images: list[str], settings: PrelabelSettings,
              mapping: dict[int, LabelClass | None], existing: str | None = None,
              sam_model: str | None = None) -> None:
        """Process `images` with settings.model; `existing` overrides settings.existing.
        With settings.sam_refine, detector boxes of polygon / mask / obb classes
        are outlined by SAM (`sam_model`, default: the one in ML Settings)."""
        if self._running:
            return
        self._sam_model = ""
        if settings.sam_refine:
            from annotator.ml import config
            self._sam_model = sam_model if sam_model is not None else config.sam_model()
        self._images = list(images)
        self._settings = settings
        self._existing = existing or settings.existing
        self._mapping = {k: v for k, v in mapping.items() if v is not None}
        self._model_name = Path(settings.model).name
        self._idx = 0
        self._cancel = False
        self._running = True
        self._t0 = time.monotonic()
        self.summary = PrelabelSummary(total=len(self._images))
        self._params = {"model": settings.model, "conf": settings.conf, "iou": settings.iou,
                        "classes": sorted(self._mapping)}
        if settings.imgsz:
            self._params["imgsz"] = settings.imgsz
        if not self._mapping:
            self.summary.fatal = "No model class is mapped to a project class."
            QTimer.singleShot(0, self._finish)
            return
        if settings.sam_refine and not (self._sam_model and Path(self._sam_model).is_file()):
            self.summary.fatal = "SAM outlines are on, but no SAM model is chosen (ML Settings)."
            QTimer.singleShot(0, self._finish)
            return
        QTimer.singleShot(0, self._next)

    def cancel(self) -> None:
        if not self._running:
            return
        self._cancel = True
        if self._rid is not None:
            self._backend.cancel(self._rid)

    # ── loop ──────────────────────────────────────────────────────────────────

    def _next(self) -> None:
        while not self._cancel and self._idx < len(self._images):
            path = self._images[self._idx]
            if self._existing == EXISTING_SKIP and self._ctrl.annotations_for(path):
                self.summary.skipped_existing += 1
                self._advance(path)
                continue
            self._rid = self._backend.request("yolo.predict", {**self._params, "image": path},
                                              on_done=lambda r, p=path: self._on_reply(p, r))
            return
        self._finish()

    def _advance(self, path: str) -> None:
        self._idx += 1
        self.progress.emit(self._idx, len(self._images), Path(path).name)

    def _on_reply(self, path: str, r: Reply) -> None:
        self._rid = None
        if not self._running:
            return
        if not r.ok:
            if self._failed(path, r):
                return
        else:
            boxes = self._boxes_for_sam(r.result)
            if boxes:                          # second step for this image: SAM outlines
                self._rid = self._backend.request(
                    "sam.boxes", {"model": self._sam_model, "image": path,
                                  "boxes": [b for _, b in boxes]},
                    on_done=lambda sr, p=path, res=r.result, b=boxes: self._on_sam(p, res, b, sr))
                return
            self._apply(path, r.result)
        self._advance(path)
        QTimer.singleShot(0, self._next)       # never recurse: thousands of images

    def _failed(self, path: str, r: Reply) -> bool:
        """Count a failed reply; True when it ended the whole run."""
        if r.error_type in _FATAL:
            if r.error_type == protocol.CANCELLED:
                self._cancel = True
            else:
                self.summary.fatal = r.message
            self._finish()
            return True
        self.summary.failed += 1
        if len(self.summary.errors) < 5:
            self.summary.errors.append(f"{Path(path).name}: {r.message}")
        return False

    def _boxes_for_sam(self, result: dict) -> list[tuple[int, list[float]]]:
        """(detection index, box) of a detector's detections that go into
        polygon / mask / obb classes — SAM turns them into outlines."""
        if not self._sam_model or result.get("task") != "detect":
            return []
        out = []
        for i, det in enumerate(result.get("detections", [])):
            lc = self._mapping.get(int(det["cls"]))
            if lc is not None and lc.annotation_type in SAM_REFINED_TYPES:
                out.append((i, [float(v) for v in det["box"]]))
        return out

    def _on_sam(self, path: str, result: dict, boxes: list, r: Reply) -> None:
        self._rid = None
        if not self._running:
            return
        if not r.ok:
            if self._failed(path, r):
                return
        else:
            dets = result["detections"]
            for (i, _), out in zip(boxes, r.result["results"]):
                if not out["polygons"]:
                    continue                   # SAM found nothing: the plain box stays
                dets[i]["polygons"] = out["polygons"]
                if self._mapping[int(dets[i]["cls"])].annotation_type == "obb":
                    dets[i]["obb"] = min_area_rect(out["polygons"][0])
                self.summary.sam_outlined += 1
            self._apply(path, result)
        self._advance(path)
        QTimer.singleShot(0, self._next)

    def _apply(self, path: str, result: dict) -> None:
        existing = self._ctrl.annotations_for(path)
        remove = ([a.id for a in existing if is_model_annotation(a)]
                  if self._existing == EXISTING_REPLACE else [])
        kept = [a for a in existing if a.id not in set(remove)]
        project = self._ctrl.project
        opts = ConvertOptions(model_name=self._model_name,
                              simplify_px=self._settings.simplify_px,
                              kpt_threshold=self._settings.kpt_threshold,
                              min_conf=self._settings.conf,
                              project_path=project.project_path if project else None,
                              image_stem=Path(path).stem)
        report = ConvertReport()
        anns = convert(result, self._mapping, opts, existing=kept, report=report)
        if anns or remove:
            self._ctrl.apply_annotation_changes(
                path, anns, remove, text=f"Pre-label ({self._model_name})")
            self.summary.changed_images.add(path)
        self.summary.processed += 1
        self.summary.added += len(anns)
        self.summary.replaced += len(remove)
        for reason, n in report.skipped.items():
            self.summary.skip_reasons[reason] = self.summary.skip_reasons.get(reason, 0) + n

    def _finish(self) -> None:
        if not self._running:
            return
        self._running = False
        self.summary.cancelled = self._cancel
        self.summary.seconds = round(time.monotonic() - self._t0, 1)
        current = self._ctrl.current_image
        if self.summary.changed_images - {current}:
            # other images were written to disk: refresh the "annotated" marks
            self._ctrl.project_changed.emit(self._ctrl.project)
        self.finished.emit(self.summary)
