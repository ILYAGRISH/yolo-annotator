"""
Object tracks across video frames (Phase 8-B).

A track is a set of annotations on frames of ONE video that share
meta["track_id"]. Annotations a person placed are KEYFRAMES
(meta["keyframe"] = True); the frames between two keyframes get
INTERPOLATED annotations (meta["keyframe"] = False, tool "interpolation")
that are re-derived whenever a keyframe changes. Editing an interpolated
annotation turns it into a keyframe.

The track covers its first..last keyframe; to end it earlier delete the
later keyframes. Interpolation needs both keyframes of the same type.
Supported types: bbox, obb, point, segment, polyline, pose
(brush masks, semantic layers and image labels can't be tracked).

Pure functions — no Qt; plan_track() says what to add / change / remove on
each frame, the caller (annotator/video/manager.py) applies it.
"""
from __future__ import annotations

import copy
import math
import uuid
from datetime import datetime

from annotator.domain.annotation import Annotation, AnnotationType

TRACKABLE = {AnnotationType.BBOX, AnnotationType.OBB, AnnotationType.POINT,
             AnnotationType.SEGMENT, AnnotationType.POLYLINE, AnnotationType.POSE}

# data keys that hold geometry (everything else — subclass, attributes… — is
# copied from the earlier keyframe)
_GEOMETRY = {
    AnnotationType.BBOX: ("x", "y", "w", "h"),
    AnnotationType.OBB: ("cx", "cy", "w", "h", "angle_deg"),
    AnnotationType.POINT: ("x", "y"),
    AnnotationType.SEGMENT: ("points",),
    AnnotationType.POLYLINE: ("points",),
    AnnotationType.POSE: ("keypoints",),
}


# ── meta helpers ──────────────────────────────────────────────────────────────

def track_id(ann: Annotation) -> int | None:
    tid = ann.meta.get("track_id")
    return tid if isinstance(tid, int) else None


def is_keyframe(ann: Annotation) -> bool:
    return track_id(ann) is not None and bool(ann.meta.get("keyframe", True))


def is_interpolated(ann: Annotation) -> bool:
    return track_id(ann) is not None and not ann.meta.get("keyframe", True)


def keyframe_meta(meta: dict, tid: int) -> dict:
    """A copy of `meta` marking the annotation a keyframe of track `tid`."""
    out = dict(meta)
    out["track_id"] = tid
    out["keyframe"] = True
    return out


def untracked_meta(meta: dict) -> dict:
    return {k: v for k, v in meta.items() if k not in ("track_id", "keyframe")}


# ── geometry interpolation ───────────────────────────────────────────────────

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_angle(a: float, b: float, t: float) -> float:
    """Degrees, along the shorter way round."""
    d = (b - a + 180.0) % 360.0 - 180.0
    return a + d * t


def _signed_area(pts) -> float:
    return 0.5 * sum(x1 * y2 - x2 * y1
                     for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))


def _resample(pts: list, n: int, closed: bool) -> list:
    """n points evenly spaced along the outline (by arc length)."""
    if len(pts) == n:
        return [list(p) for p in pts]
    path = list(pts) + ([pts[0]] if closed else [])
    seg = [math.dist(path[i], path[i + 1]) for i in range(len(path) - 1)]
    total = sum(seg)
    if total <= 0:
        return [list(pts[0]) for _ in range(n)]
    step = total / (n if closed else max(n - 1, 1))
    out, i, acc = [], 0, 0.0
    for k in range(n):
        target = k * step
        while i < len(seg) - 1 and acc + seg[i] < target:
            acc += seg[i]
            i += 1
        f = 0.0 if seg[i] == 0 else min(max((target - acc) / seg[i], 0.0), 1.0)
        (x1, y1), (x2, y2) = path[i], path[i + 1]
        out.append([_lerp(x1, x2, f), _lerp(y1, y2, f)])
    return out


def _match_outlines(a: list, b: list, closed: bool) -> tuple[list, list]:
    """Same number of points; for polygons also the same direction and the
    starting point of b rotated to best fit a."""
    n = max(len(a), len(b))
    ra, rb = _resample(a, n, closed), _resample(b, n, closed)
    if closed:
        if (_signed_area(ra) > 0) != (_signed_area(rb) > 0):
            rb = rb[::-1]
        best = min(range(n), key=lambda s: sum(
            (ra[i][0] - rb[(i + s) % n][0]) ** 2 + (ra[i][1] - rb[(i + s) % n][1]) ** 2
            for i in range(n)))
        rb = rb[best:] + rb[:best]
    return ra, rb


def interpolate_data(kind: AnnotationType, a: dict, b: dict, t: float) -> dict | None:
    """Data between keyframe data `a` (t=0) and `b` (t=1); None when the two
    can't be interpolated (different point count for pose, broken data)."""
    try:
        out = {k: copy.deepcopy(v) for k, v in a.items() if k not in _GEOMETRY.get(kind, ())}
        if kind == AnnotationType.BBOX:
            for k in ("x", "y", "w", "h"):
                out[k] = _lerp(a[k], b[k], t)
        elif kind == AnnotationType.OBB:
            for k in ("cx", "cy", "w", "h"):
                out[k] = _lerp(a[k], b[k], t)
            out["angle_deg"] = _lerp_angle(a.get("angle_deg", 0.0), b.get("angle_deg", 0.0), t)
        elif kind == AnnotationType.POINT:
            out["x"], out["y"] = _lerp(a["x"], b["x"], t), _lerp(a["y"], b["y"], t)
        elif kind in (AnnotationType.SEGMENT, AnnotationType.POLYLINE):
            pa, pb = a["points"], b["points"]
            if len(pa) < 2 or len(pb) < 2:
                return None
            ra, rb = _match_outlines(pa, pb, kind == AnnotationType.SEGMENT)
            out["points"] = [[_lerp(p[0], q[0], t), _lerp(p[1], q[1], t)]
                             for p, q in zip(ra, rb)]
        elif kind == AnnotationType.POSE:
            ka, kb = a["keypoints"], b["keypoints"]
            if len(ka) != len(kb):
                return None
            pts = []
            for (xa, ya, va), (xb, yb, vb) in zip(ka, kb):
                if va > 0 and vb > 0:
                    pts.append([_lerp(xa, xb, t), _lerp(ya, yb, t), va if t < 0.5 else vb])
                elif va > 0 and t < 0.5:
                    pts.append([xa, ya, va])
                elif vb > 0 and t >= 0.5:
                    pts.append([xb, yb, vb])
                else:
                    pts.append([0.0, 0.0, 0])
            out["keypoints"] = pts
        else:
            return None
        return out
    except (KeyError, TypeError, ValueError, IndexError):
        return None


# ── reconciling a whole track ────────────────────────────────────────────────

def _new_interpolated(src: Annotation, data: dict, tid: int) -> Annotation:
    now = datetime.utcnow().isoformat()
    return Annotation(id=str(uuid.uuid4()), class_id=src.class_id, ann_type=src.ann_type,
                      data=data,
                      meta={"created_at": now, "modified_at": now, "tool": "interpolation",
                            "source": "interpolated", "track_id": tid, "keyframe": False})


def plan_track(tid: int, frames: list) -> dict:
    """What has to change so that track `tid` is interpolated between its
    keyframes. `frames`: [(image_path, frame_number, [Annotation])] of one
    video in frame order. Returns {image_path: (upsert, remove_ids)}, only for
    frames that change; `upsert` holds new annotations and changed copies of
    existing ones (same id)."""
    keys = []                                     # [(frame_number, Annotation)]
    for _path, fno, anns in frames:
        kf = next((a for a in anns if track_id(a) == tid and is_keyframe(a)), None)
        if kf is not None:
            keys.append((fno, kf))

    plan: dict = {}
    for path, fno, anns in frames:
        mine = [a for a in anns if track_id(a) == tid and is_interpolated(a)]
        has_key = any(f == fno for f, _ in keys)
        target = None
        if not has_key:
            before = [(f, a) for f, a in keys if f < fno]
            after = [(f, a) for f, a in keys if f > fno]
            if before and after:
                (fa, ka), (fb, kb) = before[-1], after[0]
                if ka.ann_type == kb.ann_type and ka.ann_type in TRACKABLE:
                    data = interpolate_data(ka.ann_type, ka.data, kb.data, (fno - fa) / (fb - fa))
                    if data is not None:
                        target = (ka, data)
        upsert, remove = [], [a.id for a in mine]
        if target is not None:
            src, data = target
            if mine:
                cur = mine[0]
                remove = remove[1:]
                if (cur.data != data or cur.class_id != src.class_id
                        or cur.ann_type != src.ann_type):
                    upd = copy.deepcopy(cur)
                    upd.data, upd.class_id, upd.ann_type = data, src.class_id, src.ann_type
                    upd.meta["modified_at"] = datetime.utcnow().isoformat()
                    upsert.append(upd)
            else:
                upsert.append(_new_interpolated(src, data, tid))
        if upsert or remove:
            plan[path] = (upsert, remove)
    return plan


def keyframe_signature(anns) -> dict:
    """{annotation id: (track id, class, type, data)} of the keyframes in
    `anns` — compared before / after a change to see which tracks to redo."""
    return {a.id: (track_id(a), a.class_id, a.ann_type.value, repr(a.data))
            for a in anns if is_keyframe(a)}


def changed_tracks(before: dict, after: dict) -> set[int]:
    out = set()
    for aid in set(before) | set(after):
        if before.get(aid) != after.get(aid):
            for sig in (before.get(aid), after.get(aid)):
                if sig is not None:
                    out.add(sig[0])
    return out
