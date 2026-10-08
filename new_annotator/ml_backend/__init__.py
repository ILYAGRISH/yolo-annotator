"""
ML backend — runs in its own Python environment (.venv-ml or any interpreter
with torch / ultralytics) as a child process of the annotator.

Only the standard library is imported at start-up; heavy packages (torch,
ultralytics) are imported lazily by the handlers that need them, so the
backend starts instantly and still reports *why* a package is missing.

    python -u -m ml_backend.server        (cwd = new_annotator/)

See protocol.py for the wire format.
"""
