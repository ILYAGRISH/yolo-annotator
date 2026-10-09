"""
Time events on video (Phase 8-D): "from frame A to frame B — event X".

An event belongs to one imported video; `start` / `end` are frame numbers of
the source video (as ImageRecord.frame), both inclusive. It may name the
object track it is about (`track_id`, see domain/tracks.py) and carry a note.

Event types are project-wide (Project.event_types); the events themselves are
stored per video in `.annproj/events/<video_id>.json` (ProjectStore).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime

EVENT_COLORS = [
    "#FF8800", "#44AAFF", "#FF44AA", "#66DD44",
    "#AA66FF", "#FFDD00", "#00CCAA", "#FF5555",
]


@dataclass
class EventType:
    id: int
    name: str
    color: str

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "color": self.color}

    @classmethod
    def from_dict(cls, d: dict) -> "EventType":
        return cls(id=int(d["id"]), name=str(d.get("name", "")),
                   color=str(d.get("color", EVENT_COLORS[0])))


@dataclass
class VideoEvent:
    id: str
    type_id: int
    start: int                      # first frame, inclusive
    end: int                        # last frame, inclusive
    track_id: int | None = None     # object track the event is about
    note: str = ""
    meta: dict = field(default_factory=dict)    # created_at, modified_at, author

    @classmethod
    def create(cls, type_id: int, a: int, b: int, track_id: int | None = None,
               note: str = "", author: str = "") -> "VideoEvent":
        now = datetime.utcnow().isoformat()
        meta = {"created_at": now, "modified_at": now}
        if author:
            meta["author"] = author
        return cls(id=str(uuid.uuid4()), type_id=type_id, start=min(a, b), end=max(a, b),
                   track_id=track_id, note=note, meta=meta)

    def edited(self, **changes) -> "VideoEvent":
        """A copy with `changes` applied, bounds kept in order."""
        ev = replace(self, meta=dict(self.meta, modified_at=datetime.utcnow().isoformat()),
                     **changes)
        if ev.start > ev.end:
            ev.start, ev.end = ev.end, ev.start
        return ev

    def contains(self, frame: int) -> bool:
        return self.start <= frame <= self.end

    def to_dict(self) -> dict:
        d = {"id": self.id, "type_id": self.type_id, "start": self.start, "end": self.end}
        if self.track_id is not None:
            d["track_id"] = self.track_id
        if self.note:
            d["note"] = self.note
        d["meta"] = self.meta
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "VideoEvent":
        a, b = int(d["start"]), int(d["end"])
        tid = d.get("track_id")
        return cls(id=str(d["id"]), type_id=int(d["type_id"]), start=min(a, b), end=max(a, b),
                   track_id=int(tid) if tid is not None else None,
                   note=str(d.get("note", "")), meta=dict(d.get("meta", {})))


def sort_events(events: list[VideoEvent]) -> list[VideoEvent]:
    return sorted(events, key=lambda e: (e.start, e.end, e.type_id, e.id))


def pack_lanes(events: list[VideoEvent]) -> dict[str, int]:
    """Row (0, 1, …) for each event so that overlapping events never share a
    row — for drawing them on the frame strip."""
    lanes: list[int] = []                    # last frame used in each row
    out: dict[str, int] = {}
    for ev in sort_events(events):
        row = next((i for i, last in enumerate(lanes) if last < ev.start), None)
        if row is None:
            row = len(lanes)
            lanes.append(ev.end)
        else:
            lanes[row] = ev.end
        out[ev.id] = row
    return out


def seconds(frame: int, fps: float) -> float:
    return frame / fps if fps and fps > 0 else 0.0


def time_text(sec: float) -> str:
    return f"{int(sec // 60):02d}:{sec % 60:05.2f}"
