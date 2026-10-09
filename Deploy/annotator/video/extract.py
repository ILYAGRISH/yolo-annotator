"""
Video → frame images (Phase 8-B). OpenCV only, no Qt.

A video becomes ordinary project images: every `step`-th frame is written as
<folder>/<video_id>_<frame:06d>.jpg, so every tool, SAM, pre-labelling,
review and export work on frames unchanged. ImageRecord.video / .frame keep
the link back to the video (tracks, the frame strip, split by video, MOT).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import cv2

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v", ".wmv", ".mpg", ".mpeg"}


@dataclass
class VideoInfo:
    path: str
    fps: float
    frame_count: int          # as reported by the container (may be approximate)
    width: int
    height: int

    @property
    def duration(self) -> float:
        return self.frame_count / self.fps if self.fps > 0 else 0.0


def probe(path: str | Path) -> VideoInfo | None:
    """Basic properties; None when OpenCV can't open the file."""
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return None
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        if not 0 < fps < 1000:
            fps = 25.0                        # some containers report nonsense
        return VideoInfo(str(path), float(fps), int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
                         int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
                         int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0))
    finally:
        cap.release()


def video_id(path: str | Path, taken) -> str:
    """Short id from the file name — letters, digits, '-' and '_' — unique
    among `taken` (frame file names and annotation files are named after it)."""
    base = re.sub(r"[^\w\-]+", "_", Path(path).stem).strip("_") or "video"
    vid, n = base, 2
    while vid in taken:
        vid, n = f"{base}_{n}", n + 1
    return vid


def frame_name(vid: str, frame: int) -> str:
    return f"{vid}_{frame:06d}.jpg"


def frames_to_extract(frame_count: int, step: int, start: int = 0, end: int | None = None) -> int:
    end = frame_count if end is None else min(end, frame_count)
    return max(0, (end - start + step - 1) // step) if end > start else 0


def extract(path: str | Path, folder: str | Path, vid: str, step: int = 1,
            start: int = 0, end: int | None = None, quality: int = 95,
            progress=None, cancelled=None) -> list[tuple[int, str]]:
    """Write every `step`-th frame of [start, end) to `folder` as JPEG.
    `progress(done_frames_read, frame_number)` is called now and then;
    `cancelled()` → True stops early (frames written so far are kept).
    Returns [(frame_number, image_path)] in frame order."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    step = max(1, int(step))
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise OSError(f"cannot open video: {path}")
    out: list[tuple[int, str]] = []
    try:
        if start > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start)
        fno = start
        while end is None or fno < end:
            if cancelled is not None and cancelled():
                break
            want = (fno - start) % step == 0
            if want:
                ok, img = cap.read()
                if not ok:
                    break
                ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
                if ok:                       # imencode + write_bytes: any path on Windows
                    target = folder / frame_name(vid, fno)
                    target.write_bytes(buf.tobytes())
                    out.append((fno, str(target)))
            elif not cap.grab():             # skip without decoding to an image
                break
            fno += 1
            if progress is not None and (want or fno % 50 == 0):
                progress(fno - start, fno)
    finally:
        cap.release()
    return out
