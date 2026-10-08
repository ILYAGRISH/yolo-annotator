"""Ultralytics YOLO models: load and describe (phase 7-A). Prediction is 7-B.

Loaded models are cached by file path + modification time, so the same
weights are read from disk once per backend session."""
from __future__ import annotations

import os
import time
from pathlib import Path

from ml_backend.handlers import BadRequest, handler, import_or_explain, require

_MODELS: dict[str, tuple[float, object]] = {}     # resolved path -> (mtime, YOLO)


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
            "cached": cached,
            "load_seconds": round(time.perf_counter() - t0, 2),
            "device": _device()}


@handler("yolo.unload")
def unload(ctx, params):
    n = len(_MODELS)
    _MODELS.clear()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
    return {"unloaded": n}
