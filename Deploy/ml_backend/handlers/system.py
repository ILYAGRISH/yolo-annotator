"""Health check and environment report."""
from __future__ import annotations

import os
import platform
import sys
import time

from ml_backend.handlers import handler

_PACKAGES = ("torch", "torchvision", "ultralytics", "numpy", "cv2")


@handler("ping", inline=True)
def ping(ctx, params):
    return {"pong": True, "time": time.time(), "pid": os.getpid()}


@handler("system.info")
def info(ctx, params):
    """Python, package versions and the compute device. Importing torch takes a
    few seconds the first time, so this is a normal (queued) request."""
    packages = {}
    for name in _PACKAGES:
        try:
            mod = __import__(name)
            packages[name] = {"version": getattr(mod, "__version__", "?")}
        except Exception as e:              # noqa: BLE001 — report any import failure
            packages[name] = {"version": None, "error": f"{type(e).__name__}: {e}"}

    device = {"cuda": False, "gpus": [], "cuda_version": None, "mps": False}
    if packages["torch"]["version"]:
        import torch
        device["cuda"] = bool(torch.cuda.is_available())
        device["cuda_version"] = torch.version.cuda
        if device["cuda"]:
            device["gpus"] = [
                {"name": torch.cuda.get_device_name(i),
                 "memory_gb": round(torch.cuda.get_device_properties(i).total_memory / 2**30, 1)}
                for i in range(torch.cuda.device_count())]
        mps = getattr(torch.backends, "mps", None)
        device["mps"] = bool(mps and mps.is_available())

    return {"python": platform.python_version(), "executable": sys.executable,
            "platform": platform.platform(), "pid": os.getpid(),
            "packages": packages, "device": device}
