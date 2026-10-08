"""
Run every test_*.py suite and print a summary — locally and in CI.

    .venv\\Scripts\\python run_tests.py              # all suites
    .venv\\Scripts\\python run_tests.py review sam   # only suites whose name contains a word
    .venv\\Scripts\\python run_tests.py -v           # show each suite's full output

Each suite runs in its own process (they create a QApplication and their own
temporary settings), headless (QT_QPA_PLATFORM=offscreen), with UTF-8 output.
Exit code 1 if any suite fails or times out. In GitHub Actions the summary is
also written to the job page ($GITHUB_STEP_SUMMARY).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TIMEOUT = 600                       # seconds per suite

# "35 passed, 0 failed" / "Results: 109/109 passed"
_COUNT = re.compile(r"(\d+)(?:/\d+)? passed")


def run_suite(path: Path, verbose: bool) -> tuple[bool, int | None, float, str]:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    start = time.monotonic()
    try:
        proc = subprocess.run([sys.executable, path.name], cwd=HERE, env=env,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=TIMEOUT)
        out, ok = proc.stdout + proc.stderr, proc.returncode == 0
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        out += f"\nTIMEOUT after {TIMEOUT} s"
        ok = False
    seconds = time.monotonic() - start
    found = _COUNT.findall(out)
    passed = int(found[-1]) if found else None
    if verbose or not ok:
        print(out.rstrip())
    return ok, passed, seconds, out


def main(argv: list[str]) -> int:
    verbose = "-v" in argv
    words = [a.lower() for a in argv if not a.startswith("-")]
    suites = sorted(HERE.glob("test_*.py"))
    if words:
        suites = [s for s in suites if any(w in s.stem.lower() for w in words)]
    if not suites:
        print("No test suites found")
        return 1

    rows, total, failed = [], 0, []
    for path in suites:
        print(f"=== {path.name}", flush=True)
        ok, passed, seconds, _ = run_suite(path, verbose)
        total += passed or 0
        if not ok:
            failed.append(path.name)
        mark = "ok" if ok else "FAILED"
        print(f"    {mark}  {passed if passed is not None else '?'} checks  {seconds:.1f} s",
              flush=True)
        rows.append((path.name, ok, passed, seconds))

    print("\n" + "=" * 60)
    print(f"  {len(suites) - len(failed)}/{len(suites)} suites passed, {total} checks")
    if failed:
        print("  FAILED: " + ", ".join(failed))
    print("=" * 60)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### Tests — {sys.platform}, Python {sys.version.split()[0]}\n\n")
            f.write("| Suite | Result | Checks | Time |\n|---|---|---|---|\n")
            for name, ok, passed, seconds in rows:
                f.write(f"| {name} | {'✅' if ok else '❌'} | {passed if passed is not None else '?'}"
                        f" | {seconds:.1f} s |\n")
            f.write(f"\n**{len(suites) - len(failed)}/{len(suites)} suites, {total} checks**\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
