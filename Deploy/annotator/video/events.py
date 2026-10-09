"""
EventManager — time events on the current video (Phase 8-D).

    E        first press: the event starts on this frame; second press (on a
             later or earlier frame): the event ends there and is added with
             the current event type
    Shift+E  cancel the started event

Events of the current video are loaded when a frame of another video is shown
and written to `events/<video_id>.json` right after every change. Adding,
editing and deleting an event are undo steps on the controller's stack
(which, like for annotations, is cleared when the image changes).
Event types are project-wide (Project.event_types).
"""
from __future__ import annotations

try:
    from PyQt6.QtGui import QUndoCommand
except ImportError:
    from PyQt6.QtWidgets import QUndoCommand  # type: ignore[no-redef]
from PyQt6.QtCore import QObject, pyqtSignal

from annotator.domain.events import EventType, VideoEvent, sort_events
from annotator.storage.project_store import ProjectStore


class EventChangeCmd(QUndoCommand):
    """Replace `before` with `after` in a video's events (None = nothing):
    add (None → ev), edit (ev → ev'), delete (ev → None)."""

    def __init__(self, mgr: "EventManager", vid: str, before: VideoEvent | None,
                 after: VideoEvent | None, text: str):
        super().__init__(text)
        self._mgr, self._vid, self._before, self._after = mgr, vid, before, after

    def redo(self): self._mgr._raw_swap(self._vid, self._before, self._after)
    def undo(self): self._mgr._raw_swap(self._vid, self._after, self._before)


class EventManager(QObject):
    changed = pyqtSignal()               # events, types, selection or the open event changed
    status = pyqtSignal(str)             # i18n key

    def __init__(self, ctrl, video, parent=None):
        super().__init__(parent)
        self._ctrl = ctrl
        self._video = video              # VideoManager: current video, its frames
        self.vid: str = ""
        self.events: list[VideoEvent] = []
        self.open_start: int | None = None       # frame of the started, not finished event
        self.open_track: int | None = None
        self.current_type: int | None = None
        self.selected: str | None = None
        video.index_changed.connect(self._sync)
        ctrl.project_changed.connect(self._on_project_changed)

    # ── state ─────────────────────────────────────────────────────────────────

    @property
    def project(self):
        return self._ctrl.project

    @property
    def types(self) -> list[EventType]:
        return list(self.project.event_types) if self.project else []

    def current_type_obj(self) -> EventType | None:
        """The type new events get: the chosen one, else the first."""
        if not self.project:
            return None
        et = self.project.get_event_type(self.current_type) if self.current_type is not None else None
        return et or (self.project.event_types[0] if self.project.event_types else None)

    def type_of(self, ev: VideoEvent) -> EventType | None:
        return self.project.get_event_type(ev.type_id) if self.project else None

    def get(self, event_id: str | None) -> VideoEvent | None:
        return next((e for e in self.events if e.id == event_id), None)

    def selected_event(self) -> VideoEvent | None:
        return self.get(self.selected)

    def events_at(self, frame: int) -> list[VideoEvent]:
        return [e for e in self.events if e.contains(frame)]

    def fps(self) -> float:
        return float(self._video.info().get("fps") or 0.0)

    def _sync(self):
        if self._video.video != self.vid:
            self._load(self._video.video)

    def _on_project_changed(self, project):
        if project is not None and self.current_type is not None \
                and project.get_event_type(self.current_type) is None:
            self.current_type = None
        if project is None or not self._ctrl.current_image:
            self._load("")               # another project: nothing shown yet
            return
        vid = self._video.video          # VideoManager has already caught up
        self._load(vid, keep_open=vid == self.vid)

    def _load(self, vid: str, keep_open: bool = False):
        self.vid = vid
        self.events = ProjectStore.load_events(self.project, vid) if self.project and vid else []
        if not keep_open:
            self.open_start, self.open_track = None, None
        if self.get(self.selected) is None:
            self.selected = None
        self.changed.emit()

    def _save(self, vid: str, events: list[VideoEvent]):
        if self.project:
            ProjectStore.save_events(self.project, vid, events)

    def _author(self) -> str:
        try:
            return self._ctrl.reviewer() if self._ctrl.reviewer else ""
        except Exception:                # noqa: BLE001 — a name is optional
            return ""

    # ── raw change (undo commands only) ───────────────────────────────────────

    def _raw_swap(self, vid: str, old: VideoEvent | None, new: VideoEvent | None):
        events = self.events if vid == self.vid else ProjectStore.load_events(self.project, vid)
        events = [e for e in events if old is None or e.id != old.id]
        if new is not None:
            events.append(new)
        events = sort_events(events)
        self._save(vid, events)
        if vid == self.vid:
            self.events = events
            if new is not None:
                self.selected = new.id
            elif self.get(self.selected) is None:
                self.selected = None
            self.changed.emit()

    def _push(self, before, after, text):
        if not self.vid:                 # events live on video frames only
            self.status.emit("ev_not_video")
            return
        self._ctrl.undo_stack.push(EventChangeCmd(self, self.vid, before, after, text))

    # ── E / Shift+E ───────────────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        return self.open_start is not None

    def start_here(self, track: int | None = None) -> bool:
        """First E: the event starts on the current frame. `track` — the track
        of the selected annotation, if any: the event is about that object."""
        frame = self._video.frame_number()
        if not self.vid or frame < 0:
            self.status.emit("ev_not_video")
            return False
        self.open_start, self.open_track = frame, track
        self.status.emit("ev_started" if track is None else "ev_started_track")
        self.changed.emit()
        return True

    def finish_here(self) -> VideoEvent | None:
        """Second E: the event ends on the current frame (an earlier frame is
        fine too — the bounds are put in order). Needs an event type."""
        frame = self._video.frame_number()
        if not self.is_open or not self.vid or frame < 0:
            return None
        et = self.current_type_obj()
        if et is None:
            self.status.emit("ev_no_types")
            return None
        self.current_type = et.id
        ev = VideoEvent.create(et.id, self.open_start, frame, self.open_track,
                               author=self._author())
        self.open_start, self.open_track = None, None
        self._push(None, ev, f"Event {et.name}")
        self.status.emit("ev_added")
        return ev

    def cancel(self) -> bool:
        if not self.is_open:
            return False
        self.open_start, self.open_track = None, None
        self.status.emit("ev_cancelled")
        self.changed.emit()
        return True

    # ── edit ──────────────────────────────────────────────────────────────────

    def add(self, ev: VideoEvent):
        self._push(None, ev, "Add event")

    def update(self, event_id: str, **changes) -> VideoEvent | None:
        old = self.get(event_id)
        if old is None:
            return None
        new = old.edited(**changes)
        if new.to_dict() == old.to_dict() | {"meta": new.meta}:
            return old                    # nothing but the time stamp would change
        self._push(old, new, "Edit event")
        return new

    def set_bound(self, which: str) -> VideoEvent | None:
        """Start / end of the selected event := the current frame."""
        ev, frame = self.selected_event(), self._video.frame_number()
        if ev is None:
            self.status.emit("ev_select_first")
            return None
        if frame < 0:
            return None
        return self.update(ev.id, **{which: frame})

    def delete(self, event_id: str) -> bool:
        old = self.get(event_id)
        if old is None:
            return False
        self._push(old, None, "Delete event")
        return True

    def select(self, event_id: str | None):
        if event_id != self.selected:
            self.selected = event_id if self.get(event_id) else None
            self.changed.emit()

    def goto(self, event_id: str, which: str = "start") -> bool:
        """Show the first extracted frame of the event (or its last one)."""
        ev = self.get(event_id)
        if ev is None or not self._video.frames:
            return False
        inside = [(p, f) for p, f in self._video.frames if ev.contains(f)]
        if inside:
            target = inside[0] if which == "start" else inside[-1]
        else:                            # no frame inside: the nearest one
            ref = ev.start if which == "start" else ev.end
            target = min(self._video.frames, key=lambda pf: abs(pf[1] - ref))
        self._video.navigate.emit(target[0])
        return True

    def goto_event(self, direction: int) -> bool:
        """Previous / next event start relative to the current frame."""
        here = self._video.frame_number()
        starts = sorted(self.events, key=lambda e: e.start)
        cand = ([e for e in starts if e.start > here] if direction > 0
                else [e for e in starts if e.start < here][::-1])
        if not cand:
            return False
        self.select(cand[0].id)
        return self.goto(cand[0].id)

    # ── event types (project-wide, not undo steps) ────────────────────────────

    def _save_project(self):
        if self.project and self.project.project_path:
            ProjectStore.save(self.project, self.project.project_path)

    def set_current_type(self, type_id: int | None):
        if type_id != self.current_type:
            self.current_type = type_id
            self.changed.emit()

    def add_type(self, name: str, color: str | None = None) -> EventType | None:
        name = name.strip()
        if not self.project or not name:
            return None
        same = next((t for t in self.project.event_types if t.name == name), None)
        et = same or self.project.add_event_type(name, color)
        if same is None:
            self._save_project()
        self.current_type = et.id
        self.changed.emit()
        return et

    def edit_type(self, type_id: int, name: str | None = None, color: str | None = None):
        et = self.project.get_event_type(type_id) if self.project else None
        if et is None:
            return
        if name and name.strip():
            et.name = name.strip()
        if color:
            et.color = color
        self._save_project()
        self.changed.emit()

    def _video_ids(self) -> list[str]:
        return list(self.project.videos) if self.project else []

    def type_usage(self, type_id: int) -> int:
        """How many events of all videos have this type."""
        return sum(1 for vid in self._video_ids()
                   for e in (self.events if vid == self.vid
                             else ProjectStore.load_events(self.project, vid))
                   if e.type_id == type_id)

    def delete_type(self, type_id: int) -> int:
        """Remove the type and every event of it in all videos (no undo);
        returns how many events went."""
        if not self.project:
            return 0
        removed = 0
        for vid in self._video_ids():
            events = self.events if vid == self.vid else ProjectStore.load_events(self.project, vid)
            keep = [e for e in events if e.type_id != type_id]
            if len(keep) != len(events):
                removed += len(events) - len(keep)
                self._save(vid, keep)
                if vid == self.vid:
                    self.events = keep
        self.project.event_types = [t for t in self.project.event_types if t.id != type_id]
        self._save_project()
        if self.current_type == type_id:
            self.current_type = None
        if self.get(self.selected) is None:
            self.selected = None
        self._ctrl.undo_stack.clear()    # undo steps may still name the removed events
        self.changed.emit()
        return removed

    def counts(self) -> dict[str, int]:
        """{video id: number of events} for every video of the project."""
        return {vid: len(self.events if vid == self.vid
                         else ProjectStore.load_events(self.project, vid))
                for vid in self._video_ids()}
