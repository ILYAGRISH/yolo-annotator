"""
Video events exporter (Phase 8-D) — time events of imported videos.

    <out>/events.csv           one row per event:
        video,video_file,event_id,type,start_frame,end_frame,start_sec,end_sec,
        duration_sec,track_id,note,subset
    <out>/activitynet.json     ActivityNet 1.3 layout:
        {"version": "1.3",
         "taxonomy": [{"nodeId", "nodeName", "parentId", "parentName"}],
         "database": {<video id>: {"subset", "duration", "url", "resolution",
                                   "fps", "annotations": [{"segment": [s, e], "label", …}]}}}
    <out>/event_types.txt      type names, one per line (order of the taxonomy)
    with copy_images:
    <out>/videos/<file>        the source video (when it is still on disk)
    <out>/frames/<video id>/   its extracted frames

Frames are frame numbers of the source video; seconds = frame / fps, the end
is the time of the event's last frame. `subset` (training / validation /
testing) is the split of the video's frames — the one most of them are in.
"""
from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from pathlib import Path

from annotator.domain.events import seconds
from annotator.exporters.base import BaseExporter
from annotator.storage.project_store import ProjectStore

SUBSETS = {"train": "training", "val": "validation", "test": "testing"}


class VideoEventsExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "Video Events"

    @property
    def file_extension(self) -> str:
        return ".csv"

    def export(self, project, output_dir: Path, **kwargs):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        copy_media = kwargs.get("copy_images", False)
        types = {t.id: t for t in project.event_types}
        self.events = 0
        self.copied = 0
        rows = []
        database = {}
        for vid, info in project.videos.items():
            recs = [r for r in project.images if r.video == vid]
            fps = float(info.get("fps") or 0.0)
            split = Counter(r.split or "train" for r in recs).most_common(1)
            subset = SUBSETS.get(split[0][0], split[0][0]) if split else "training"
            path = info.get("path", "")
            anns = []
            for e in ProjectStore.load_events(project, vid):
                et = types.get(e.type_id)
                if et is None:
                    continue
                s, t = round(seconds(e.start, fps), 3), round(seconds(e.end, fps), 3)
                rows.append([vid, Path(path).name, e.id, et.name, e.start, e.end, s, t,
                             round(t - s, 3), "" if e.track_id is None else e.track_id,
                             e.note, subset])
                a = {"segment": [s, t], "label": et.name,
                     "frames": [e.start, e.end], "id": e.id}
                if e.track_id is not None:
                    a["track_id"] = e.track_id
                if e.note:
                    a["note"] = e.note
                anns.append(a)
            self.events += len(anns)
            if copy_media:
                self._copy_media(output_dir, vid, path, recs)
            frames = info.get("frame_count") or 0
            database[vid] = {
                "subset": subset,
                "duration": round(seconds(frames, fps), 3),
                "url": path,
                "resolution": f"{info.get('width', 0)}x{info.get('height', 0)}",
                "fps": fps,
                "annotations": anns,
            }

        with open(output_dir / "events.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["video", "video_file", "event_id", "type", "start_frame", "end_frame",
                        "start_sec", "end_sec", "duration_sec", "track_id", "note", "subset"])
            w.writerows(rows)
        ordered = sorted(types.values(), key=lambda t: t.id)
        taxonomy = [{"nodeId": i + 1, "nodeName": t.name, "parentId": 0, "parentName": "Root"}
                    for i, t in enumerate(ordered)]
        taxonomy.insert(0, {"nodeId": 0, "nodeName": "Root", "parentId": None, "parentName": None})
        with open(output_dir / "activitynet.json", "w", encoding="utf-8") as f:
            json.dump({"version": "1.3", "taxonomy": taxonomy, "database": database},
                      f, indent=2, ensure_ascii=False)
        (output_dir / "event_types.txt").write_text(
            "".join(f"{t.name}\n" for t in ordered), encoding="utf-8")

    def _copy_media(self, output_dir: Path, vid: str, video_path: str, recs):
        """The source video into videos/, its frames into frames/<vid>/."""
        src = Path(video_path) if video_path else None
        if src is not None and src.is_file():
            dst = output_dir / "videos" / src.name
            dst.parent.mkdir(exist_ok=True)
            if not dst.exists() or dst.stat().st_size != src.stat().st_size:
                shutil.copy2(src, dst)
            self.copied += 1
        for rec in sorted(recs, key=lambda r: r.frame):
            p = Path(rec.path)
            if p.is_file():
                folder = output_dir / "frames" / vid
                folder.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, folder / p.name)
                self.copied += 1
