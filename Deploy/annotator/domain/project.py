import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from annotator.domain.events import EVENT_COLORS, EventType
from annotator.domain.label_class import LabelClass

FORMAT_VERSION = 3

DEFAULT_HOTKEYS: dict[str, str] = {
    "navigate_next":  "D",
    "navigate_prev":  "A",
    "view_fit":       "F",
    "tool_select":    "V",
    "tool_polygon":   "P",
    "tool_polyline":  "L",
    "tool_bbox":      "B",
    "tool_obb":       "O",
    "tool_crack":     "C",
    "tool_pose":      "K",
    "tool_point":     ".",
    "tool_brush":     "M",
    "tool_semantic":  "S",
    "tool_fill":      "G",
    "review_accept":      "R",
    "review_accept_all":  "Shift+R",
    "review_next":        "U",
    "track_start":        "T",
    "track_keyframe":     "Shift+T",
    "track_prev_key":     "Shift+A",
    "track_next_key":     "Shift+D",
    "event_mark":         "E",
    "event_cancel":       "Shift+E",
}

_DEFAULT_COLORS = [
    "#FF4444", "#44DD44", "#4488FF", "#FFDD00",
    "#FF44FF", "#00DDDD", "#FF8800", "#8844FF",
    "#44FF99", "#FF4499", "#99FF44", "#4499FF",
]

DEFAULT_CLASS_NAME = "object"   # the one class a new project starts with


def unique_stem(path: str, taken: set[str]) -> str:
    """
    A file stem for `path` not yet in `taken` (compared case-insensitively —
    Windows file names are), and add it there. The plain stem when free, else
    "<parent folder>_<stem>", else that with "_2", "_3", …
    road_a/frame.jpg → "frame", then road_b/frame.jpg → "road_b_frame".
    """
    stem = Path(path).stem
    parent = re.sub(r"[^\w\-]+", "_", Path(path).parent.name).strip("_")
    candidates = [stem] + ([f"{parent}_{stem}"] if parent else [])
    for c in candidates:
        if c.casefold() not in taken:
            taken.add(c.casefold())
            return c
    base, n = candidates[-1], 2
    while f"{base}_{n}".casefold() in taken:
        n += 1
    taken.add(f"{base}_{n}".casefold())
    return f"{base}_{n}"


@dataclass
class ImageRecord:
    path: str
    width: int = 0
    height: int = 0
    split: str = "train"
    video: str = ""         # id in Project.videos when the image is a video frame
    frame: int = -1         # frame number in that video (0-based)
    # Unique name of the image inside the project: annotations/<key>.json,
    # multi-user assignments, exported file names. The file stem unless another
    # image already has it (same name in another folder) — see unique_stem().
    key: str = ""

    @property
    def ann_key(self) -> str:
        return self.key or Path(self.path).stem

    def to_dict(self) -> dict:
        d = {"path": self.path, "width": self.width,
             "height": self.height, "split": self.split}
        if self.video:                       # plain images keep the old layout
            d["video"], d["frame"] = self.video, self.frame
        if self.key and self.key != Path(self.path).stem:
            d["key"] = self.key              # only for renamed duplicates
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ImageRecord":
        return cls(path=d["path"], width=d.get("width", 0),
                   height=d.get("height", 0), split=d.get("split", "train"),
                   video=d.get("video", ""), frame=d.get("frame", -1),
                   key=d.get("key", ""))


@dataclass
class ProjectSettings:
    default_export_format: str = "auto"
    autosave_interval_sec: int = 60
    image_folder: str = ""
    hotkeys: dict = field(default_factory=lambda: dict(DEFAULT_HOTKEYS))

    def to_dict(self) -> dict:
        return {
            "default_export_format": self.default_export_format,
            "autosave_interval_sec": self.autosave_interval_sec,
            "image_folder": self.image_folder,
            "hotkeys": self.hotkeys,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectSettings":
        hk = {**DEFAULT_HOTKEYS, **d.get("hotkeys", {})}
        return cls(
            default_export_format=d.get("default_export_format", "auto"),
            autosave_interval_sec=d.get("autosave_interval_sec", 60),
            image_folder=d.get("image_folder", ""),
            hotkeys=hk,
        )


@dataclass
class Project:
    id: str
    name: str
    created_at: str
    modified_at: str
    # classes live in class_schema.json; loaded by ProjectStore and placed here at runtime
    classes: list[LabelClass] = field(default_factory=list)
    images: list[ImageRecord] = field(default_factory=list)
    settings: ProjectSettings = field(default_factory=ProjectSettings)
    leader_machine: str = field(default="")  # hostname of first opener; "" = unclaimed
    # imported videos: id → {"path", "fps", "frame_count", "width", "height",
    # "step", "folder"} (see annotator/video/extract.py)
    videos: dict = field(default_factory=dict)
    next_track_id: int = 1                   # track ids are unique per project
    # types of time events on video (Phase 8-D); the events themselves are
    # stored per video in events/<video_id>.json
    event_types: list[EventType] = field(default_factory=list)

    # Runtime-only
    project_path: Path | None = field(default=None, repr=False)
    _keys: dict | None = field(default=None, repr=False, compare=False)   # path → key
    # images that got a new key when this (old) project was opened: they had
    # shared an annotation file with a same-named image (see ensure_image_keys)
    dup_renamed: list = field(default_factory=list, repr=False, compare=False)

    @classmethod
    def create(cls, name: str) -> "Project":
        now = datetime.utcnow().isoformat()
        proj = cls(id=str(uuid.uuid4()), name=name,
                   created_at=now, modified_at=now)
        proj.add_class(DEFAULT_CLASS_NAME)
        return proj

    # ── class management ──────────────────────────────────────────────────────

    def add_class(self, name: str, color: str | None = None) -> LabelClass:
        next_id = max((c.id for c in self.classes), default=-1) + 1
        color = color or _DEFAULT_COLORS[next_id % len(_DEFAULT_COLORS)]
        lc = LabelClass(id=next_id, name=name, color=color)
        self.classes.append(lc)
        return lc

    def remove_class(self, class_id: int):
        self.classes = [c for c in self.classes if c.id != class_id]

    def get_class(self, class_id: int) -> LabelClass | None:
        return next((c for c in self.classes if c.id == class_id), None)

    # ── image management ──────────────────────────────────────────────────────

    def add_image(self, path: str, width: int = 0, height: int = 0) -> ImageRecord:
        keys = self._key_index()
        if path in keys:
            return next(r for r in self.images if r.path == path)
        taken = {k.casefold() for k in keys.values()}
        rec = ImageRecord(path=path, width=width, height=height,
                          key=unique_stem(path, taken))
        self.images.append(rec)
        keys[path] = rec.key
        return rec

    def image_key(self, path: str) -> str:
        """Unique name of a project image (file stem for paths not in the project)."""
        return self._key_index().get(path) or Path(path).stem

    def ensure_image_keys(self) -> list[str]:
        """
        Give every image without a key one (images.json written before keys
        existed). The first image with a name keeps it, later ones with the
        same name get "<folder>_<name>". Returns the paths that got such a new
        name — in an old project they shared one annotation file with another image.
        """
        taken = {r.key.casefold() for r in self.images if r.key}
        renamed = []
        for r in self.images:
            if not r.key:
                r.key = unique_stem(r.path, taken)
                if r.key != Path(r.path).stem:
                    renamed.append(r.path)
        self._keys = None
        return renamed

    def _key_index(self) -> dict:
        if self._keys is None or len(self._keys) != len(self.images):
            if any(not r.key for r in self.images):
                self.ensure_image_keys()
            self._keys = {r.path: r.key for r in self.images}
        return self._keys

    # ── event types (Phase 8-D) ───────────────────────────────────────────────

    def add_event_type(self, name: str, color: str | None = None) -> EventType:
        next_id = max((t.id for t in self.event_types), default=-1) + 1
        et = EventType(id=next_id, name=name,
                       color=color or EVENT_COLORS[next_id % len(EVENT_COLORS)])
        self.event_types.append(et)
        return et

    def get_event_type(self, type_id: int) -> EventType | None:
        return next((t for t in self.event_types if t.id == type_id), None)

    # ── serialization (project.json only — no classes) ────────────────────────

    def to_dict(self) -> dict:
        self.modified_at = datetime.utcnow().isoformat()
        return {
            "format_version": FORMAT_VERSION,
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "settings": self.settings.to_dict(),
            "leader_machine": self.leader_machine,
            "videos": self.videos,
            "next_track_id": self.next_track_id,
            "event_types": [t.to_dict() for t in self.event_types],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        return cls(
            id=d["id"],
            name=d["name"],
            created_at=d["created_at"],
            modified_at=d["modified_at"],
            settings=ProjectSettings.from_dict(d.get("settings", {})),
            leader_machine=d.get("leader_machine", ""),
            videos=d.get("videos", {}),
            next_track_id=d.get("next_track_id", 1),
            event_types=[EventType.from_dict(t) for t in d.get("event_types", [])],
        )
