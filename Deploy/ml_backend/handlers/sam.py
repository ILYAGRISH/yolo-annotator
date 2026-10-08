"""Segment Anything (SAM, SAM 2 / 2.1, MobileSAM via Ultralytics): a mask from
clicks and / or a box (7-C, sam.predict), or one mask per box for many boxes
of one image (7-D, sam.boxes).

The image encoder is the slow part (~0.06 s on a GPU, seconds on a CPU); its
result is kept for the last image, so every further click on the same image
only runs the prompt decoder (~15 ms on a GPU).

sam.predict returns geometry in PIXELS of the original image, like yolo.predict:

    {"width": W, "height": H, "ms": 16.0, "embed_ms": 0.0,
     "score": 0.93,                                   # SAM's own mask quality
     "box": [x1, y1, x2, y2],                         # bounding box of the mask
     "polygons": [[[x, y], ...], ...]}                # every part, largest first

sam.boxes: {"width", "height", "ms", "embed_ms", "results": [{score, box, polygons}]}
— one result per input box, same order.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from ml_backend.handlers import BadRequest, handler, import_or_explain, require
from ml_backend.handlers.yolo import _device, _mask_polygons, _read_image

_STATE: dict = {"model": None, "predictor": None, "image": None, "size": None}


def _predictor_class(stem: str):
    """SAM 2 / 2.1 weights are named sam2*; sam_b / sam_l / mobile_sam are SAM 1."""
    import_or_explain("ultralytics")
    from ultralytics.models.sam import Predictor, SAM2Predictor
    if "sam3" in stem:
        raise BadRequest("SAM 3 is not supported yet — use SAM 2.1 (sam2.1_b.pt) or MobileSAM")
    if "fastsam" in stem.lower():
        raise BadRequest("FastSAM is a different model family — use SAM 2.1 (sam2.1_b.pt) or MobileSAM")
    return SAM2Predictor if "sam2" in stem else Predictor


def get_predictor(path_str: str):
    """Return (predictor, was_cached) for these weights (path + mtime)."""
    path = Path(path_str)
    if not path.is_file():
        raise BadRequest(f"model file not found: {path_str}")
    key = (str(path.resolve()), path.stat().st_mtime)
    if _STATE["model"] == key:
        return _STATE["predictor"], True
    cls = _predictor_class(path.stem)
    predictor = cls(overrides=dict(task="segment", mode="predict", imgsz=1024, conf=0.0,
                                   model=key[0], save=False, verbose=False))
    predictor.setup_model(verbose=False)
    _STATE.update(model=key, predictor=predictor, image=None, size=None, warm=False)
    return predictor, False


def _set_image(predictor, image_path: str) -> float:
    """Encode the image unless it is the one already encoded; returns ms spent."""
    p = Path(image_path)
    if not p.is_file():
        raise BadRequest(f"image not found: {image_path}")
    key = (str(p.resolve()), p.stat().st_mtime)
    if _STATE["image"] == key:
        return 0.0
    t0 = time.perf_counter()
    img = _read_image(image_path)
    predictor.set_image(img)
    _STATE["image"], _STATE["size"] = key, (img.shape[1], img.shape[0])
    if not _STATE.get("warm"):                   # the first decoder run is ~15x slower:
        predictor(points=[[[img.shape[1] / 2, img.shape[0] / 2]]], labels=[[1]])
        _STATE["warm"] = True                    # pay it here, not on the first click
    return (time.perf_counter() - t0) * 1000


@handler("sam.load_model")
def load_model(ctx, params):
    path = require(params, "path", str)
    t0 = time.perf_counter()
    _, cached = get_predictor(path)
    return {"path": os.path.abspath(path), "cached": cached,
            "load_seconds": round(time.perf_counter() - t0, 2), "device": _device()}


@handler("sam.set_image")
def set_image(ctx, params):
    """Encode an image ahead of the first click (called when it is opened)."""
    predictor, _ = get_predictor(require(params, "model", str))
    ms = _set_image(predictor, require(params, "image", str))
    w, h = _STATE["size"]
    return {"width": w, "height": h, "embed_ms": round(ms, 1)}


@handler("sam.predict")
def predict(ctx, params):
    predictor, _ = get_predictor(require(params, "model", str))
    embed_ms = _set_image(predictor, require(params, "image", str))
    ctx.check_cancel()
    points = params.get("points") or []
    labels = params.get("labels") or []
    box = params.get("box")
    if len(points) != len(labels):
        raise BadRequest("points and labels differ in length")
    if not points and not box:
        raise BadRequest("give at least one point or a box")
    kwargs = {}
    if points:                                   # one object: shape (1, N, 2) / (1, N)
        kwargs["points"] = [[[float(x), float(y)] for x, y in points]]
        kwargs["labels"] = [[int(v) for v in labels]]
    if box:
        if len(box) != 4:
            raise BadRequest("box must be [x1, y1, x2, y2]")
        kwargs["bboxes"] = [[float(v) for v in box]]
    t0 = time.perf_counter()
    result = predictor(**kwargs)[0]
    ms = (time.perf_counter() - t0) * 1000
    w, h = _STATE["size"]
    out = {"width": w, "height": h, "ms": round(ms, 1), "embed_ms": round(embed_ms, 1),
           "score": 0.0, "box": None, "polygons": []}
    if result.masks is None or len(result.masks) == 0:
        return out
    scores = result.boxes.conf.tolist() if result.boxes is not None else [0.0]
    best = max(range(len(scores)), key=lambda i: scores[i])
    out.update(_mask_result(result.masks.data[best], scores[best]))
    return out


_BOX_BATCH = 32                                  # boxes per decoder run (GPU memory)


@handler("sam.boxes")
def boxes(ctx, params):
    """One mask per box, in the order given: {"results": [{score, box, polygons}]}
    (an empty polygons list where SAM found nothing). Used to turn detector /
    existing boxes into outlines."""
    predictor, _ = get_predictor(require(params, "model", str))
    embed_ms = _set_image(predictor, require(params, "image", str))
    items = params.get("boxes") or []
    if not isinstance(items, list) or any(not isinstance(b, list) or len(b) != 4 for b in items):
        raise BadRequest("boxes must be a list of [x1, y1, x2, y2]")
    t0 = time.perf_counter()
    results = []
    for start in range(0, len(items), _BOX_BATCH):
        ctx.check_cancel()
        chunk = [[float(v) for v in b] for b in items[start:start + _BOX_BATCH]]
        result = predictor(bboxes=chunk)[0]
        n = 0 if result.masks is None else len(result.masks)
        scores = result.boxes.conf.tolist() if result.boxes is not None else []
        for i in range(len(chunk)):
            results.append(_mask_result(result.masks.data[i], scores[i] if i < len(scores) else 0.0)
                           if i < n else {"score": 0.0, "box": None, "polygons": []})
    w, h = _STATE["size"]
    return {"width": w, "height": h, "ms": round((time.perf_counter() - t0) * 1000, 1),
            "embed_ms": round(embed_ms, 1), "results": results}


def _mask_result(mask, score) -> dict:
    polygons = _mask_polygons(mask.cpu().numpy(), min_area=16.0)   # no specks
    box = None
    if polygons:
        xs = [x for poly in polygons for x, _ in poly]
        ys = [y for poly in polygons for _, y in poly]
        box = [min(xs), min(ys), max(xs), max(ys)]
    return {"score": round(float(score), 4), "box": box, "polygons": polygons}


@handler("sam.unload")
def unload(ctx, params):
    had = _STATE["predictor"] is not None
    _STATE.update(model=None, predictor=None, image=None, size=None, warm=False)
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
    return {"unloaded": int(had)}
