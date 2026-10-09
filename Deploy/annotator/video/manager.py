"""
VideoManager — tracks on the frames of the current video (Phase 8-B).

Keeps a small index of the current video (which frames hold which tracks,
keyframe or interpolated, how many annotations), re-interpolates a track
whenever one of its keyframes changes on the current frame — by an edit,
a delete, an undo or a redo — and implements the track commands:

    T        start a track from the selected annotation
    Shift+T  keyframe of the active track on this frame (copies the nearest
             keyframe when the track has nothing here yet)
    Shift+A / Shift+D   previous / next keyframe of the active track

Interpolated annotations are derived data: written with
ProjectController.sync_derived (not an undo step) and recomputed from the
keyframes, so undo / redo of a keyframe edit re-derives them as well.
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from annotator.domain.annotation import Annotation
from annotator.domain.tracks import (TRACKABLE, changed_tracks, is_keyframe,
                                     keyframe_meta, keyframe_signature,
                                     plan_track, track_id)


class VideoManager(QObject):
    index_changed = pyqtSignal()           # frames / tracks / active track changed
    frames_written = pyqtSignal(list)      # [(image_path, [Annotation])] written to disk
    navigate = pyqtSignal(str)             # please show this image
    status = pyqtSignal(str)

    def __init__(self, ctrl, allowed=None, parent=None):
        super().__init__(parent)
        self._ctrl = ctrl
        self._allowed = allowed            # callable → set of paths this user may change, or None
        self.video: str = ""               # id of the current video ("" = not a video frame)
        self.frames: list[tuple[str, int]] = []      # [(path, frame_number)] in order
        self.marks: dict[str, dict[int, bool]] = {}  # path → {track id: is keyframe}
        self.counts: dict[str, int] = {}             # path → number of annotations
        self.active_track: int | None = None
        self._track_cls: dict[int, int] = {}          # track id → class id (from keyframes)
        self._sig: dict = {}
        self._pending: set[int] = set()
        ctrl.image_changed.connect(self._on_image_changed)
        ctrl.annotations_changed.connect(self._on_annotations_changed)
        ctrl.project_changed.connect(self._on_project_changed)

    # ── state ─────────────────────────────────────────────────────────────────

    def record(self, path: str | None = None):
        project = self._ctrl.project
        path = path or self._ctrl.current_image
        if not project or not path:
            return None
        return next((r for r in project.images if r.path == path), None)

    def info(self) -> dict:
        return (self._ctrl.project.videos.get(self.video, {})
                if self._ctrl.project and self.video else {})

    def frame_number(self, path: str | None = None) -> int:
        rec = self.record(path)
        return rec.frame if rec else -1

    def keyframes(self, tid: int | None = None) -> list[tuple[str, int]]:
        tid = self.active_track if tid is None else tid
        return [(p, f) for p, f in self.frames if self.marks.get(p, {}).get(tid) is True]

    def track_frames(self, tid: int | None = None) -> list[tuple[str, int]]:
        tid = self.active_track if tid is None else tid
        return [(p, f) for p, f in self.frames if tid in self.marks.get(p, {})]

    def track_class(self, tid: int | None = None):
        """Class of the track (as seen on its keyframes), or None."""
        tid = self.active_track if tid is None else tid
        cid = self._track_cls.get(tid)
        return self._ctrl.project.get_class(cid) if cid is not None and self._ctrl.project else None

    @property
    def track_color(self) -> str | None:
        cls = self.track_class()
        return cls.color if cls else None

    # ── controller signals ────────────────────────────────────────────────────

    def _on_project_changed(self, project):
        if project is None:
            self._set_video("")
            return
        if self._ctrl.current_image:            # frames / annotations may have changed on disk
            self._rebuild(force=True)

    def _on_image_changed(self, path: str, anns: list):
        self._rebuild()
        self._sig = keyframe_signature(anns)
        self._note(path, anns)
        self.index_changed.emit()

    def _on_annotations_changed(self, anns: list):
        path = self._ctrl.current_image
        if not path or not self.video:
            return
        self._note(path, anns)
        sig = keyframe_signature(anns)
        changed = changed_tracks(self._sig, sig)
        self._sig = sig
        if changed:
            # after the whole undo macro / command, not in the middle of it
            if not self._pending:
                QTimer.singleShot(0, self._flush)
            self._pending |= changed
        self.index_changed.emit()

    def _flush(self):
        tids, self._pending = self._pending, set()
        for tid in sorted(t for t in tids if t is not None):
            self.recompute(tid)

    # ── index ─────────────────────────────────────────────────────────────────

    def _set_video(self, vid: str):
        if vid != self.video:
            self.active_track = None
        self.video = vid
        if not vid:
            self.frames, self.marks, self.counts = [], {}, {}
            self._track_cls = {}

    def _rebuild(self, force: bool = False):
        rec = self.record()
        vid = rec.video if rec else ""
        if vid == self.video and not force:
            return
        self._set_video(vid)
        if not vid:
            return
        project = self._ctrl.project
        recs = sorted((r for r in project.images if r.video == vid), key=lambda r: r.frame)
        self.frames = [(r.path, r.frame) for r in recs]
        self.marks, self.counts = {}, {}
        for path, _f in self.frames:
            self._note(path, self._ctrl.annotations_for(path))
        if self.active_track is not None and not self.track_frames():
            self.active_track = None
        self.index_changed.emit()

    def _note(self, path: str, anns: list):
        self.counts[path] = len(anns)
        m = {}
        for a in anns:
            tid = track_id(a)
            if tid is not None:
                m[tid] = m.get(tid, False) or is_keyframe(a)
                self._track_cls[tid] = a.class_id
        if m:
            self.marks[path] = m
        else:
            self.marks.pop(path, None)

    # ── interpolation ─────────────────────────────────────────────────────────

    def recompute(self, tid: int) -> int:
        """Re-derive the interpolated frames of track `tid`; returns how many
        frames changed."""
        if not self.video:
            return 0
        keys = [f for p, f in self.keyframes(tid)]
        lo, hi = (min(keys), max(keys)) if keys else (0, -1)
        involved = [(p, f) for p, f in self.frames
                    if lo <= f <= hi or tid in self.marks.get(p, {})]
        frames = [(p, f, self._ctrl.annotations_for(p)) for p, f in involved]
        plan = plan_track(tid, frames)
        allowed = self._allowed() if self._allowed else None
        written = []
        for path, (upsert, remove) in plan.items():
            if allowed is not None and path not in allowed:
                continue
            self._ctrl.sync_derived(path, upsert, remove)
            anns = self._ctrl.annotations_for(path)
            self._note(path, anns)
            if path != self._ctrl.current_image:
                written.append((path, anns))
        if self._ctrl.current_image:
            self._sig = keyframe_signature(self._ctrl.current_annotations)
        if written:
            self.frames_written.emit(written)
        self.index_changed.emit()
        return len(plan)

    # ── commands ──────────────────────────────────────────────────────────────

    def set_active_from(self, ann: Annotation | None):
        """Selecting a track annotation makes its track the active one (it
        stays active across frames until another track is selected)."""
        tid = track_id(ann) if ann is not None else None
        if tid is not None and tid != self.active_track:
            self.active_track = tid
            self.index_changed.emit()

    def start_track(self, ann_id: str) -> int | None:
        """T: the selected annotation becomes keyframe of a new track."""
        ann = self._ctrl.get_annotation(ann_id) if ann_id else None
        if ann is None:
            self.status.emit("track_select_first")
            return None
        if not self.video:
            self.status.emit("track_not_video")
            return None
        if ann.ann_type not in TRACKABLE:
            self.status.emit("track_not_trackable")
            return None
        if track_id(ann) is not None:
            self.active_track = track_id(ann)
            self.index_changed.emit()
            self.status.emit("track_already")
            return self.active_track
        tid = self._ctrl.new_track_id()
        self.active_track = tid
        self._ctrl.set_meta({ann.id: keyframe_meta(ann.meta, tid)}, f"Start track #{tid}")
        self.status.emit("track_started")
        return tid

    def keyframe_here(self) -> Annotation | None:
        """Shift+T: keyframe of the active track on the current frame."""
        tid, path = self.active_track, self._ctrl.current_image
        if tid is None:
            self.status.emit("track_none_active")
            return None
        if not self.video or not path:
            self.status.emit("track_not_video")
            return None
        mine = [a for a in self._ctrl.current_annotations if track_id(a) == tid]
        if any(is_keyframe(a) for a in mine):
            self.status.emit("track_already_key")
            return next(a for a in mine if is_keyframe(a))
        if mine:                                   # interpolated → keyframe as it is
            a = mine[0]
            meta = dict(a.meta, keyframe=True, source="manual", tool="track")
            self._ctrl.set_meta({a.id: meta}, f"Keyframe #{tid}")
            self._ctrl.select_annotation(a.id)
            return a
        here = self.frame_number(path)
        keys = self.keyframes(tid)
        if not keys:
            self.status.emit("track_none_active")
            return None
        before = [k for k in keys if k[1] < here]
        src_path = (before[-1] if before else keys[0])[0]
        src = next((a for a in self._ctrl.annotations_for(src_path)
                    if track_id(a) == tid and is_keyframe(a)), None)
        if src is None:
            return None
        now = datetime.utcnow().isoformat()
        meta = {"created_at": now, "modified_at": now, "tool": "track", "source": "manual"}
        new = Annotation(id=str(uuid.uuid4()), class_id=src.class_id, ann_type=src.ann_type,
                         data=copy.deepcopy(src.data), meta=keyframe_meta(meta, tid))
        self._ctrl.add_annotation(new)
        self._ctrl.select_annotation(new.id)
        self.status.emit("track_key_added")
        return new

    def goto_keyframe(self, direction: int) -> bool:
        """Shift+A / Shift+D: previous (-1) / next (+1) keyframe of the active
        track; without one — previous / next annotated frame."""
        here = self.frame_number()
        if not self.video:
            return False
        if self.active_track is not None:
            cand = self.keyframes()
        else:
            cand = [(p, f) for p, f in self.frames if self.counts.get(p)]
        cand = ([c for c in cand if c[1] > here] if direction > 0
                else [c for c in cand if c[1] < here][::-1])
        if not cand:
            return False
        self.navigate.emit(cand[0][0])
        return True

    def goto_frame_index(self, index: int):
        if 0 <= index < len(self.frames):
            self.navigate.emit(self.frames[index][0])

    def current_index(self) -> int:
        path = self._ctrl.current_image
        return next((i for i, (p, _f) in enumerate(self.frames) if p == path), -1)

    def delete_track(self, tid: int) -> int:
        """Remove every annotation of track `tid` (all frames)."""
        cur = self._ctrl.current_image
        removed = 0
        allowed = self._allowed() if self._allowed else None
        paths = [p for p, _f in self.track_frames(tid)]
        for path in sorted(paths, key=lambda p: p == cur):        # current image last
            if allowed is not None and path not in allowed:
                continue
            ids = [a.id for a in self._ctrl.annotations_for(path) if track_id(a) == tid]
            if path == cur:
                self._ctrl.apply_annotation_changes(path, [], ids, text=f"Delete track #{tid}")
            else:
                self._ctrl.apply_annotation_changes(path, [], ids)
                anns = self._ctrl.annotations_for(path)
                self._note(path, anns)
                self.frames_written.emit([(path, anns)])
            removed += len(ids)
        if self.active_track == tid:
            self.active_track = None
        self.index_changed.emit()
        return removed

    def time_text(self, path: str | None = None) -> str:
        fps = self.info().get("fps") or 0
        f = self.frame_number(path)
        if fps <= 0 or f < 0:
            return ""
        sec = f / fps
        return f"{int(sec // 60):02d}:{sec % 60:05.2f}"

    def video_name(self) -> str:
        return Path(self.info().get("path", self.video)).name if self.video else ""
