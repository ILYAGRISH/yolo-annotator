"""Ultralytics YOLO models: load / describe (7-A) and predict (7-B).

Loaded models are cached by file path + modification time, so the same
weights are read from disk once per backend session.

yolo.predict returns geometry in PIXELS of the original image — the client
normalises it and maps it onto project classes:

    {"width": W, "height": H, "task": "segment", "ms": 12.3,
     "detections": [{"cls": 0, "conf": 0.91,
                     "box": [x1, y1, x2, y2],
                     "polygons": [[[x, y], ...], ...],    # segment: every part
                     "obb": [cx, cy, w, h, angle_rad],     # obb
                     "keypoints": [[x, y, conf], ...]}],   # pose
     "classification": [{"cls": 3, "conf": 0.8}, ...]}    # classify: top-5

yolo.track (8-C) takes the same parameters for ONE frame of a video plus
"reset" (true on the first frame) and "tracker" ("bytetrack" / "botsort");
its detections carry "track_id" — the tracker's own number, consistent
across the frames of one run.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from ml_backend.handlers import BadRequest, handler, import_or_explain, require

_MODELS: dict[str, tuple[float, object]] = {}     # resolved path -> (mtime, YOLO)
# tracking runs on its OWN model instance: Ultralytics attaches the tracker to
# the model for good (callbacks), it would alter later yolo.predict calls
_TRACK: dict = {}                                    # {"key", "mtime", "tracker", "model"}
TRACKERS = ("bytetrack", "botsort")


def get_model(path_str: str):
    """Return (model, was_cached). Raises BadRequest / MissingPackage."""
    path = Path(path_str)
    if not path.is_file():
        raise BadRequest(f"model file not found: {path_str}")
    key = str(path.resolve())
    mtime = path.stat().st_mtime
    cached = _MODELS.get(key)
    if cached and cached[0] == mtime:
        return cached[1], True
    ultralytics = import_or_explain("ultralytics")
    model = ultralytics.YOLO(key)
    _MODELS[key] = (mtime, model)
    return model, False


def _device() -> str:
    import torch
    if torch.cuda.is_available():
        return f"cuda: {torch.cuda.get_device_name(0)}"
    mps = getattr(torch.backends, "mps", None)
    if mps and mps.is_available():
        return "mps"
    return "cpu"


@handler("yolo.load_model")
def load_model(ctx, params):
    path = require(params, "path", str)
    t0 = time.perf_counter()
    model, cached = get_model(path)
    names = model.names                               # {id: name} (list for some exports)
    items = names.items() if isinstance(names, dict) else enumerate(names)
    classes = [{"id": int(i), "name": str(n)} for i, n in sorted(items)]
    return {"path": os.path.abspath(path),
            "task": model.task,                       # detect / segment / pose / obb / classify
            "classes": classes,
            "kpt_shape": _kpt_shape(model),           # pose: [K, 2|3], else None
            "cached": cached,
            "load_seconds": round(time.perf_counter() - t0, 2),
            "device": _device()}


def _kpt_shape(model):
    inner = getattr(model, "model", None)
    shape = getattr(inner, "kpt_shape", None)
    if shape is None:
        shape = (getattr(inner, "yaml", None) or {}).get("kpt_shape")
    return [int(v) for v in shape] if shape else None


def _read_image(path: str):
    """BGR array; np.fromfile + imdecode also works for non-ASCII Windows paths."""
    np = import_or_explain("numpy")
    cv2 = import_or_explain("cv2")
    if not os.path.isfile(path):
        raise BadRequest(f"image not found: {path}")
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise BadRequest(f"cannot read image: {path}")
    return img


def _mask_polygons(mask, min_area: float = 4.0) -> list:
    """Outer contour of every connected part of a binary mask, in pixels."""
    import cv2
    import numpy as np
    m = (mask > 0.5).astype(np.uint8) if mask.dtype != np.uint8 else mask
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polys = []
    for c in sorted(contours, key=cv2.contourArea, reverse=True):
        if cv2.contourArea(c) < min_area:
            continue
        c = cv2.approxPolyDP(c, 1.0, True)          # drop points closer than ~1 px to the line
        if len(c) >= 3:
            polys.append([[float(x), float(y)] for x, y in c.reshape(-1, 2)])
    return polys


def _kwargs(params) -> dict:
    kwargs = {"conf": float(params.get("conf", 0.25)),
              "iou": float(params.get("iou", 0.7)),
              "max_det": int(params.get("max_det", 300)),
              "verbose": False,
              "retina_masks": True}                  # masks at the original resolution
    if params.get("imgsz"):
        kwargs["imgsz"] = int(params["imgsz"])
    if params.get("classes") is not None:
        kwargs["classes"] = [int(c) for c in params["classes"]]
    if params.get("device"):
        kwargs["device"] = str(params["device"])
    return kwargs


@handler("yolo.predict")
def predict(ctx, params):
    model_path = require(params, "model", str)
    image = require(params, "image", str)
    model, _ = get_model(model_path)
    img = _read_image(image)
    t0 = time.perf_counter()
    res = model.predict(img, **_kwargs(params))[0]
    return _result(ctx, model, res, (time.perf_counter() - t0) * 1000)


def _track_model(path_str: str, tracker: str, reset: bool):
    """The tracking instance; a new one (fresh tracker) on reset, other
    weights or another tracker."""
    path = Path(path_str)
    if not path.is_file():
        raise BadRequest(f"model file not found: {path_str}")
    key, mtime = str(path.resolve()), path.stat().st_mtime
    if (reset or _TRACK.get("key") != key or _TRACK.get("mtime") != mtime
            or _TRACK.get("tracker") != tracker):
        ultralytics = import_or_explain("ultralytics")
        _TRACK.clear()
        _TRACK.update(key=key, mtime=mtime, tracker=tracker, model=ultralytics.YOLO(key))
    return _TRACK["model"]


@handler("yolo.track")
def track(ctx, params):
    model_path = require(params, "model", str)
    image = require(params, "image", str)
    tracker = str(params.get("tracker", "bytetrack"))
    if tracker not in TRACKERS:
        raise BadRequest(f"unknown tracker: {tracker} (use {', '.join(TRACKERS)})")
    model = _track_model(model_path, tracker, bool(params.get("reset")))
    if model.task == "classify":
        raise BadRequest("a classification model can't track objects")
    img = _read_image(image)
    t0 = time.perf_counter()
    res = model.track(img, persist=True, tracker=f"{tracker}.yaml", **_kwargs(params))[0]
    return _result(ctx, model, res, (time.perf_counter() - t0) * 1000)


def _ids(part) -> list | None:
    ids = getattr(part, "id", None)
    return None if ids is None else [int(v) for v in ids.cpu().numpy().tolist()]


def _result(ctx, model, res, ms: float) -> dict:
    cv2 = import_or_explain("cv2")
    h, w = (int(v) for v in res.orig_shape)
    out = {"width": w, "height": h, "task": model.task, "ms": round(ms, 1),
           "detections": [], "classification": []}

    if res.probs is not None:
        for c, p in zip(res.probs.top5, res.probs.top5conf.cpu().numpy().tolist()):
            out["classification"].append({"cls": int(c), "conf": float(p)})
        return out

    if res.obb is not None:
        xywhr = res.obb.xywhr.cpu().numpy()
        corners = res.obb.xyxyxyxy.cpu().numpy()
        ids = _ids(res.obb)
        for i, (cls, conf) in enumerate(zip(res.obb.cls.cpu().numpy(), res.obb.conf.cpu().numpy())):
            xs, ys = corners[i][:, 0], corners[i][:, 1]
            det = {"cls": int(cls), "conf": float(conf),
                   "box": [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())],
                   "obb": [float(v) for v in xywhr[i]]}
            if ids is not None:
                det["track_id"] = ids[i]
            out["detections"].append(det)
        return out

    boxes = res.boxes
    if boxes is None:
        return out
    xyxy = boxes.xyxy.cpu().numpy()
    masks = res.masks.data.cpu().numpy() if res.masks is not None else None
    kpts = res.keypoints
    kxy = kpts.xy.cpu().numpy() if kpts is not None else None
    kconf = kpts.conf.cpu().numpy() if kpts is not None and kpts.conf is not None else None
    ids = _ids(boxes)
    for i, (cls, conf) in enumerate(zip(boxes.cls.cpu().numpy(), boxes.conf.cpu().numpy())):
        ctx.check_cancel()
        det = {"cls": int(cls), "conf": float(conf), "box": [float(v) for v in xyxy[i]]}
        if ids is not None:
            det["track_id"] = ids[i]
        if masks is not None:
            m = masks[i]
            if m.shape != (h, w):                    # safety: retina_masks should match
                m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
            det["polygons"] = _mask_polygons(m)
        if kxy is not None:
            det["keypoints"] = [[float(x), float(y),
                                 float(kconf[i][k]) if kconf is not None else 1.0]
                                for k, (x, y) in enumerate(kxy[i])]
        out["detections"].append(det)
    return out


@handler("yolo.unload")
def unload(ctx, params):
    n = len(_MODELS) + (1 if _TRACK else 0)
    _MODELS.clear()
    _TRACK.clear()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
    return {"unloaded": n}
