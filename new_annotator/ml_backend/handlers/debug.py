"""Diagnostic methods — used by the tests and handy for checking a new
environment by hand. They never touch models or files."""
from __future__ import annotations

import os
import sys
import time

from ml_backend.handlers import handler


@handler("debug.echo")
def echo(ctx, params):
    return params


@handler("debug.sleep")
def sleep(ctx, params):
    """A long job: `steps` x `delay` s with progress events, cancellable."""
    steps = int(params.get("steps", 10))
    delay = float(params.get("delay", 0.1))
    for i in range(steps):
        ctx.check_cancel()
        time.sleep(delay)
        ctx.progress(i + 1, steps, f"step {i + 1}/{steps}")
    return {"steps": steps}


@handler("debug.fail")
def fail(ctx, params):
    raise RuntimeError(params.get("message", "intentional failure"))


@handler("debug.noisy")
def noisy(ctx, params):
    """Writes junk to stdout the way libraries do — must not break the protocol."""
    print("python-level print to stdout")
    sys.stdout.write("sys.stdout.write without newline")
    os.write(1, b"C-level write to fd 1\n")
    return {"ok": True}


@handler("debug.exit")
def exit_process(ctx, params):
    """Simulates a hard crash (e.g. CUDA out-of-memory killing the process)."""
    os._exit(int(params.get("code", 3)))
