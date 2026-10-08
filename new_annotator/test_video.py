"""
Video frames and tracks (phase 8-B): extraction, project model, interpolation,
track reconciliation, controller, VideoManager, MOT export, split by video,
main window (menu, timeline, import dialog).
Run: .venv/Scripts/python test_video.py
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))
_TMP = Path(tempfile.mkdtemp())
os.environ["ANNOTATOR_SETTINGS"] = str(_TMP / "settings.ini")

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

import cv2
import numpy as np

_pass = _fail = 0

def check(name: str, ok: bool):
    global _pass, _fail
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if ok:
        _pass += 1
    else:
        _fail += 1

def section(title: str):
    print(f"\n--- {title} ---")

def pump(ms=20):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()

def wait(pred, timeout=20.0) -> bool:
    end = time.monotonic() + timeout
    while not pred():
        if time.monotonic() > end:
            return False
        pump(10)
    return True

def close(a, b, eps=1e-6):
    return abs(a - b) < eps

W, H, FPS, N = 160, 120, 25, 50

def make_video(path: Path):
    """A white 30x40 box moving 2 px right per frame on a coloured background."""
    path.parent.mkdir(parents=True, exist_ok=True)
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for i in range(N):
        f = np.zeros((H, W, 3), np.uint8)
        f[:, :] = (40, 90, 140)
        cv2.rectangle(f, (10 + 2 * i, 40), (10 + 2 * i + 30, 80), (255, 255, 255), -1)
        w.write(f)
    w.release()

VIDEO = _TMP / "Видео" / "улица 1.mp4"          # non-ASCII on purpose
make_video(VIDEO)

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.video.extract import (extract, frame_name, frames_to_extract, probe,
                                     video_id)


# ═════════════════════════════════════════════════════════════════════════════
section("1. Extracting frames")
# ═════════════════════════════════════════════════════════════════════════════
info = probe(VIDEO)
check("probe reads size, fps and length",
      info is not None and (info.width, info.height) == (W, H)
      and close(info.fps, FPS) and info.frame_count == N and close(info.duration, 2.0))
check("probe of a missing / broken file -> None",
      probe(_TMP / "nope.mp4") is None)
bad = _TMP / "broken.mp4"
bad.write_bytes(b"not a video")
check("probe of garbage -> None", probe(bad) is None)
check("video id from the name: safe characters", video_id(VIDEO, set()) == "улица_1")
check("video id unique in the project", video_id(VIDEO, {"улица_1", "улица_1_2"}) == "улица_1_3")
check("frame file name", frame_name("v", 7) == "v_000007.jpg")
check("frames_to_extract", (frames_to_extract(50, 5), frames_to_extract(50, 5, 10, 30),
                            frames_to_extract(50, 1, 40, 30)) == (10, 4, 0))
out = extract(VIDEO, _TMP / "fr", "vid", step=5)
check("every 5th frame written", [f for f, _ in out] == list(range(0, 50, 5)))
check("files exist under a non-ASCII folder too", all(Path(p).exists() for _, p in out))
img = cv2.imdecode(np.fromfile(out[2][1], np.uint8), cv2.IMREAD_COLOR)
col = int(np.argmax(img[60, :, 0] > 200))
check("the right frame content (box at x = 10 + 2*frame)", abs(col - (10 + 2 * 10)) <= 2)
part = extract(VIDEO, _TMP / "fr2", "vid", step=4, start=10, end=30)
check("range [start, end) with a step", [f for f, _ in part] == [10, 14, 18, 22, 26])
seen = []
stopped = extract(VIDEO, _TMP / "fr3", "vid", step=1,
                  progress=lambda n, f: seen.append(n), cancelled=lambda: len(seen) >= 5)
check("cancel stops early, keeps what was written", 0 < len(stopped) < N and seen)
try:
    extract(bad, _TMP / "fr4", "x")
    check("unreadable video raises", False)
except OSError:
    check("unreadable video raises", True)


# ═════════════════════════════════════════════════════════════════════════════
section("2. Project model")
# ═════════════════════════════════════════════════════════════════════════════
from annotator.domain.project import ImageRecord, Project
plain = ImageRecord("a.jpg", 10, 10)
check("plain image: old json layout", set(plain.to_dict()) == {"path", "width", "height", "split"})
fr = ImageRecord("b.jpg", 10, 10, video="v", frame=12)
back = ImageRecord.from_dict(fr.to_dict())
check("frame record round trip", (back.video, back.frame) == ("v", 12))
check("old record without video keys", ImageRecord.from_dict({"path": "x"}).video == "")
p = Project.create("p")
p.videos["v"] = {"fps": 25.0}
p.next_track_id = 7
q = Project.from_dict(p.to_dict())
check("videos and next_track_id saved in project.json",
      q.videos == {"v": {"fps": 25.0}} and q.next_track_id == 7)
check("older project.json -> defaults", Project.from_dict(
    {k: v for k, v in p.to_dict().items() if k not in ("videos", "next_track_id")}).next_track_id == 1)


# ═════════════════════════════════════════════════════════════════════════════
section("3. Interpolation")
# ═════════════════════════════════════════════════════════════════════════════
from annotator.domain.tracks import (changed_tracks, interpolate_data, is_interpolated,
                                     is_keyframe, keyframe_meta, keyframe_signature,
                                     plan_track, track_id, untracked_meta)
B, O, P, S, L, K = (AnnotationType.BBOX, AnnotationType.OBB, AnnotationType.POINT,
                    AnnotationType.SEGMENT, AnnotationType.POLYLINE, AnnotationType.POSE)
d = interpolate_data(B, {"x": 0, "y": 0, "w": .2, "h": .2, "subclass": "red"},
                     {"x": .4, "y": .2, "w": .4, "h": .2}, .25)
check("bbox: linear", close(d["x"], .1) and close(d["y"], .05) and close(d["w"], .25))
check("non-geometry data copied from the earlier keyframe", d["subclass"] == "red")
d = interpolate_data(O, {"cx": .5, "cy": .5, "w": .2, "h": .1, "angle_deg": 350},
                     {"cx": .5, "cy": .5, "w": .2, "h": .1, "angle_deg": 10}, .5)
check("obb: angle the short way round (350 -> 10 passes 0)", close(d["angle_deg"] % 360, 0))
d = interpolate_data(P, {"x": 0, "y": 0}, {"x": 1, "y": .5}, .5)
check("point", close(d["x"], .5) and close(d["y"], .25))
sq = [[0, 0], [1, 0], [1, 1], [0, 1]]
d = interpolate_data(S, {"points": sq}, {"points": [[x + 1, y] for x, y in sq]}, .5)
check("polygon, same points: shifted halfway",
      sorted(map(tuple, d["points"])) == sorted((x + .5, y) for x, y in sq))
d = interpolate_data(S, {"points": sq}, {"points": [[x + 1, y] for x, y in sq[::-1]]}, .5)
check("polygon drawn the other way round still matches",
      sorted(map(tuple, (tuple(round(v, 6) for v in pt) for pt in d["points"])))
      == sorted((x + .5, y) for x, y in sq))
tri = [[0, 0], [2, 0], [1, 2]]
d = interpolate_data(S, {"points": sq}, {"points": tri}, .5)
check("polygon with a different point count is resampled", len(d["points"]) == 4)
d = interpolate_data(L, {"points": [[0, 0], [1, 0]]}, {"points": [[0, 1], [1, 1], [2, 1]]}, .5)
check("polyline resampled, ends kept", len(d["points"]) == 3
      and close(d["points"][0][1], .5) and close(d["points"][-1][0], 1.5))
d = interpolate_data(K, {"keypoints": [[0, 0, 2], [.5, .5, 2], [0, 0, 0]]},
                     {"keypoints": [[1, 1, 2], [0, 0, 0], [1, 1, 2]]}, .25)
check("pose: visible both -> linear; hidden later -> kept first half; appears later -> hidden",
      close(d["keypoints"][0][0], .25) and d["keypoints"][1] == [.5, .5, 2]
      and d["keypoints"][2][2] == 0)
check("pose with different point counts -> None",
      interpolate_data(K, {"keypoints": [[0, 0, 2]]}, {"keypoints": []}, .5) is None)
check("mask can't be interpolated", interpolate_data(AnnotationType.MASK, {}, {}, .5) is None)
check("broken data -> None", interpolate_data(B, {"x": 0}, {"x": 1}, .5) is None)


# ═════════════════════════════════════════════════════════════════════════════
section("4. Reconciling a track")
# ═════════════════════════════════════════════════════════════════════════════
def bx(x, tid=None, key=True, cid=0):
    a = Annotation.new(cid, B, {"x": x, "y": .1, "w": .2, "h": .2})
    if tid is not None:
        a.meta = keyframe_meta(a.meta, tid)
        a.meta["keyframe"] = key
    return a

frames = [(f"f{i}", i * 5, []) for i in range(5)]      # frame numbers 0,5,10,15,20
frames[0][2].append(bx(0.0, 1))
frames[4][2].append(bx(0.4, 1))
plan = plan_track(1, frames)
check("frames between keyframes get one annotation each", sorted(plan) == ["f1", "f2", "f3"])
mid = plan["f2"][0][0]
check("interpolated by frame number", close(mid.data["x"], .2) and is_interpolated(mid)
      and track_id(mid) == 1 and mid.meta["tool"] == "interpolation")
for path, (ups, rem) in plan.items():                   # apply
    dict((p, a) for p, _f, a in frames)[path].extend(ups)
check("nothing to do when already in step", plan_track(1, frames) == {})
frames[4][2][0].data["x"] = .8                          # move the last keyframe
plan2 = plan_track(1, frames)
upd = plan2["f2"][0][0]
check("moving a keyframe updates in place (same id, nothing removed)",
      upd.id == mid.id and close(upd.data["x"], .4) and plan2["f2"][1] == [])
frames[2][2][:] = [bx(.9, 1)]                          # a keyframe in the middle
plan3 = plan_track(1, frames)
check("a new middle keyframe splits the interpolation",
      close(plan3["f1"][0][0].data["x"], .45) and close(plan3["f3"][0][0].data["x"], .85))
frames[4][2][:] = [a for a in frames[4][2] if False]  # drop the last keyframe
for path, (ups, rem) in plan_track(1, frames).items():
    pass
plan4 = plan_track(1, frames)
check("frames after the last keyframe lose their interpolation",
      "f3" in plan4 and plan4["f3"][0] == [] and len(plan4["f3"][1]) == 1)
other = [("g0", 0, [bx(0, 2)]), ("g1", 1, [bx(0, 2, key=False)])]
check("interpolated without keyframes on both sides are removed",
      plan_track(2, other) == {"g1": ([], [other[1][2][0].id])})
mixed = [("h0", 0, [bx(0, 3)]), ("h1", 1, []),
         ("h2", 2, [Annotation(id="o", class_id=0, ann_type=O,
                               data={"cx": .5, "cy": .5, "w": .1, "h": .1, "angle_deg": 0},
                               meta={"track_id": 3, "keyframe": True})])]
check("keyframes of different types: no interpolation", plan_track(3, mixed) == {})
a = bx(0, 5)
check("meta helpers", is_keyframe(a) and not is_interpolated(a) and track_id(a) == 5
      and "track_id" not in untracked_meta(a.meta) and track_id(bx(0)) is None)
s1 = keyframe_signature([a, bx(.1, 6, key=False), bx(.2)])
check("signature lists keyframes only", list(s1) == [a.id])
b = Annotation.from_dict(a.to_dict())
b.data["x"] = .3
check("changed_tracks finds edits, adds and deletes",
      changed_tracks(s1, keyframe_signature([b])) == {5}
      and changed_tracks(s1, {}) == {5} and changed_tracks({}, s1) == {5}
      and changed_tracks(s1, s1) == set())


# ═════════════════════════════════════════════════════════════════════════════
section("5. Controller")
# ═════════════════════════════════════════════════════════════════════════════
from annotator.controller.project_controller import ProjectController
from annotator.storage.project_store import ProjectStore
ctrl = ProjectController()
proj = ctrl.create_project("vid", _TMP / "vid.annproj")
frames10 = extract(VIDEO, _TMP / "frames", "street", step=5)
meta = {"path": str(VIDEO), "fps": 25.0, "frame_count": N, "width": W, "height": H,
        "step": 5, "folder": str(_TMP / "frames")}
changed = []
ctrl.project_changed.connect(lambda p: changed.append(1))
n = ctrl.add_video_frames("street", meta, frames10)
check("frames added as images with video and frame number",
      n == 10 and [(r.video, r.frame) for r in proj.images][:2] == [("street", 0), ("street", 5)])
check("video registered; project saved and refreshed",
      proj.videos["street"]["fps"] == 25.0 and changed
      and json.loads((proj.project_path / "images.json").read_text("utf-8"))[1]["frame"] == 5)
t1, t2 = ctrl.new_track_id(), ctrl.new_track_id()
check("track ids increase and are saved at once",
      (t1, t2) == (1, 2) and ProjectStore.load(proj.project_path).next_track_id == 3)
paths = [r.path for r in proj.images]
ctrl.set_image(paths[3])
interp = bx(.3, 9, key=False)
interp.meta["source"] = "interpolated"
before = ctrl.undo_stack.count()
ctrl.sync_derived(paths[3], [interp], [])
check("sync_derived on the current image: no undo step",
      ctrl.undo_stack.count() == before and ctrl.get_annotation(interp.id) is not None)
upd = Annotation.from_dict(interp.to_dict())
upd.data["x"] = .35
ctrl.sync_derived(paths[3], [upd], [])
check("sync_derived replaces by id", len(ctrl.current_annotations) == 1
      and close(ctrl.get_annotation(interp.id).data["x"], .35))
ctrl.update_annotation_data(interp.id, dict(upd.data, x=.5))
e = ctrl.get_annotation(interp.id)
check("editing an interpolated annotation makes it a keyframe (source manual)",
      is_keyframe(e) and e.meta["source"] == "manual")
ctrl.undo_stack.undo()
check("undo: interpolated again", is_interpolated(ctrl.get_annotation(interp.id)))
ctrl.sync_derived(paths[3], [], [interp.id])
check("sync_derived removes", ctrl.current_annotations == [])
other_ann = bx(.6, 9, key=False)
ctrl.sync_derived(paths[5], [other_ann], [])
check("sync_derived on another image writes the file and YOLO labels",
      [a.id for a in ProjectStore.load_annotations(proj, paths[5])] == [other_ann.id]
      and (Path(paths[5]).parent / "labels" / (Path(paths[5]).stem + ".txt")).exists())
ctrl.sync_derived(paths[5], [], [other_ann.id])
before = ctrl.undo_stack.count()
ctrl.set_meta({}, "nothing")
check("set_meta with nothing pushes no step", ctrl.undo_stack.count() == before)


# ═════════════════════════════════════════════════════════════════════════════
section("6. VideoManager: tracks end to end")
# ═════════════════════════════════════════════════════════════════════════════
from annotator.video.manager import VideoManager
mgr = VideoManager(ctrl)
statuses, navs = [], []
mgr.status.connect(statuses.append)
mgr.navigate.connect(navs.append)
mgr.navigate.connect(ctrl.set_image)
ctrl.set_image(paths[0])
check("index of the current video", mgr.video == "street" and len(mgr.frames) == 10
      and mgr.frame_number() == 0 and mgr.current_index() == 0)
check("time text", mgr.time_text(paths[2]) == "00:00.40")
check("video name", mgr.video_name() == "улица 1.mp4")
k0 = bx(.1)
ctrl.add_annotation(k0)
check("T without a selection explains", mgr.start_track("") is None
      and statuses[-1] == "track_select_first")
tid = mgr.start_track(k0.id)
pump()
check("T: the annotation becomes keyframe of a new active track",
      tid == 3 and mgr.active_track == 3 and is_keyframe(ctrl.get_annotation(k0.id))
      and mgr.keyframes() == [(paths[0], 0)])
check("track class known for the strip", mgr.track_class().id == 0 and mgr.track_color)
check("T on a track annotation just activates it",
      mgr.start_track(k0.id) == 3 and statuses[-1] == "track_already")
ctrl.undo_stack.undo()
pump()
check("undo of T: no longer a track", track_id(ctrl.get_annotation(k0.id)) is None)
ctrl.undo_stack.redo()
pump()
ctrl.set_image(paths[4])                               # frame 20
check("active track survives a frame change", mgr.active_track == 3)
new = mgr.keyframe_here()
pump()
check("Shift+T copies the keyframe here and selects it",
      new is not None and is_keyframe(ctrl.get_annotation(new.id))
      and close(ctrl.get_annotation(new.id).data["x"], .1))
check("copy of an identical keyframe: frames in between hold the same box",
      all(close(a.data["x"], .1) for p in paths[1:4] for a in ctrl.annotations_for(p)))
ctrl.update_annotation_data(new.id, dict(new.data, x=.5))     # move it
pump()
xs = [ctrl.annotations_for(p)[0].data["x"] for p in paths[1:4]]
check("moving the keyframe re-interpolates frames 5, 10, 15",
      all(close(x, v) for x, v in zip(xs, (.2, .3, .4))))
check("in-between frames are interpolated, labelled with the track",
      all(is_interpolated(ctrl.annotations_for(p)[0]) for p in paths[1:4]))
check("index knows track frames", len(mgr.track_frames()) == 5 and len(mgr.keyframes()) == 2)
ctrl.undo_stack.undo()
pump()
check("undo of the move re-derives the frames in between",
      all(close(ctrl.annotations_for(p)[0].data["x"], .1) for p in paths[1:4]))
ctrl.undo_stack.redo()
pump()
check("Shift+T again on a keyframe frame", mgr.keyframe_here() is not None
      and statuses[-1] == "track_already_key")
ctrl.set_image(paths[2])
mid_ann = ctrl.current_annotations[0]
ctrl.update_annotation_data(mid_ann.id, dict(mid_ann.data, y=.5))   # edit in between
pump()
check("editing an in-between frame turns it into a keyframe",
      is_keyframe(ctrl.get_annotation(mid_ann.id)) and len(mgr.keyframes()) == 3)
check("neighbours re-interpolated toward it",
      close(ctrl.annotations_for(paths[1])[0].data["y"], .3)
      and close(ctrl.annotations_for(paths[3])[0].data["y"], .3))
ctrl.set_image(paths[4])
ctrl.delete_annotation(new.id)                          # delete the last keyframe
pump()
check("deleting the last keyframe ends the track at the previous one",
      ctrl.annotations_for(paths[3]) == [] and len(mgr.track_frames()) == 3)
ctrl.undo_stack.undo()
pump()
check("undo brings the keyframe and its interpolation back",
      len(ctrl.annotations_for(paths[3])) == 1 and len(mgr.track_frames()) == 5)
ctrl.set_image(paths[0])
navs.clear()
check("next keyframe (Shift+D)", mgr.goto_keyframe(1) and navs[-1] == paths[2])
check("previous keyframe (Shift+A)", mgr.goto_keyframe(-1) and navs[-1] == paths[0])
check("no keyframe before the first", not mgr.goto_keyframe(-1))
mgr.goto_frame_index(7)
check("go to a frame by index", ctrl.current_image == paths[7])
ctrl.set_image(paths[6])                                 # outside the track
check("Shift+T on a frame outside the track copies the nearest earlier keyframe",
      close(mgr.keyframe_here().data["x"], .5))
pump()
check("track now reaches frame 30", len(mgr.track_frames()) == 7)
ctrl.set_image(paths[9])
mgr.active_track = None
check("Shift+T without an active track explains",
      mgr.keyframe_here() is None and statuses[-1] == "track_none_active")
mask = Annotation.new(0, AnnotationType.MASK, {"mask_png_path": "", "polygon": [], "bbox": [0, 0, 0, 0]})
ctrl.add_annotation(mask)
check("masks can't be tracked", mgr.start_track(mask.id) is None
      and statuses[-1] == "track_not_trackable")
ctrl.set_image(paths[0])
mgr.set_active_from(ctrl.current_annotations[0])
check("selecting a track annotation activates its track", mgr.active_track == 3)
plain_img = _TMP / "plain.png"
cv2.imwrite(str(plain_img), np.zeros((10, 10, 3), np.uint8))
ctrl.add_images_from_paths([plain_img])
ctrl.set_image(str(plain_img))
check("plain image: no video, no active track", mgr.video == "" and mgr.active_track is None)
pa = Annotation.new(0, B, {"x": 0, "y": 0, "w": .1, "h": .1})
ctrl.add_annotation(pa)
check("T on a plain image explains", mgr.start_track(pa.id) is None
      and statuses[-1] == "track_not_video")


# ═════════════════════════════════════════════════════════════════════════════
section("7. MOT export")
# ═════════════════════════════════════════════════════════════════════════════
ctrl.set_image(paths[0])
ctrl.add_annotation(bx(.7))                              # not a track: not exported
out = _TMP / "mot"
ctrl.export_dataset(out, "mot", copy_images=True)
gt = (out / "street" / "gt" / "gt.txt").read_text().splitlines()
check("one gt line per track box", len(gt) == 7)
f1 = gt[0].split(",")
check("gt line: frame 1, id 3, box in pixels, class 1",
      f1[0] == "1" and f1[1] == "3" and close(float(f1[2]), .1 * W, .01)
      and close(float(f1[4]), .2 * W, .01) and f1[7] == "1")
check("frame numbers follow the extracted frames (1-based)",
      [int(l.split(",")[0]) for l in gt] == [1, 2, 3, 4, 5, 6, 7])
ini = (out / "street" / "seqinfo.ini").read_text()
check("seqinfo: rate = fps / step, length, size",
      "frameRate=5" in ini and "seqLength=10" in ini and f"imWidth={W}" in ini)
check("images renumbered in img1", (out / "street" / "img1" / "000010.jpg").exists())
check("frames.csv maps back to video frames",
      (out / "street" / "frames.csv").read_text().splitlines()[2].startswith("2,5,"))
check("classes.txt", (out / "classes.txt").read_text().startswith("1 object"))
from annotator.exporters.mot import pixel_box
obb = Annotation.new(0, O, {"cx": .5, "cy": .5, "w": .2, "h": .2, "angle_deg": 45})
bxo = pixel_box(obb, 100, 100)
check("OBB box = its rotated corners' bounds", close(bxo[2], 20 * 2 ** .5, 1e-6))
check("point has no box", pixel_box(Annotation.new(0, P, {"x": .5, "y": .5}), 10, 10) is None)
pose = Annotation.new(0, K, {"keypoints": [[.1, .1, 2], [.5, .9, 2], [.9, .9, 0]]})
check("pose box from visible keypoints", pixel_box(pose, 10, 10) == (1.0, 1.0, 4.0, 8.0))


# ═════════════════════════════════════════════════════════════════════════════
section("8. Split by video")
# ═════════════════════════════════════════════════════════════════════════════
frames_b = extract(VIDEO, _TMP / "frames_b", "b", step=10)
ctrl.add_video_frames("b", dict(meta, step=10), frames_b)
for i in range(4):
    pi = _TMP / f"single{i}.png"
    cv2.imwrite(str(pi), np.zeros((8, 8, 3), np.uint8))
    ctrl.add_images_from_paths([pi])
ctrl.split_dataset(30, 0, "all", True, by_video=True)
by_vid = {}
for r in proj.images:
    if r.video:
        by_vid.setdefault(r.video, set()).add(r.split)
check("every video's frames share one split", all(len(s) == 1 for s in by_vid.values()))
check("the big video stays in train, the small one goes to val",
      by_vid["street"] == {"train"} and by_vid["b"] == {"val"})
ctrl.split_dataset(70, 0, "all", False, by_video=False)
check("by_video off: frames of a video can be split",
      len({r.split for r in proj.images if r.video == "street"}) == 2)


# ═════════════════════════════════════════════════════════════════════════════
section("9. Main window")
# ═════════════════════════════════════════════════════════════════════════════
from PyQt6.QtWidgets import QDialog
import annotator.ui.main_window as mw
win = mw.MainWindow()
wc = win.controller
wc.open_project(proj.project_path)
pump()
check("Video menu shortcuts", [a.shortcut().toString() for a in
      (win._act_track_start, win._act_track_key, win._act_track_prev, win._act_track_next)]
      == ["T", "Shift+T", "Shift+A", "Shift+D"])
win._goto_image(paths[1])
pump()
check("timeline visible on a video frame", not win._timeline.isHidden()
      and "street" not in win._timeline._info.text() and "улица 1.mp4" in win._timeline._info.text())
win._video.set_active_from(next(a for a in wc.current_annotations if track_id(a) == 3))
win._timeline.refresh()
check("timeline names the active track", "#3" in win._timeline._track.text())
item = win._scene._ann_items[wc.current_annotations[0].id]
check("canvas label shows the track (#3, interpolated)",
      item.label.endswith("#3") and not item.label.endswith("◆"))
check("annotations panel shows the track",
      "#3" in win._annotations_panel._list.item(0).text())
from PyQt6.QtGui import QImage, QPainter
img = QImage(400, 40, QImage.Format.Format_ARGB32)
win._timeline._bar.resize(400, 30)
qp = QPainter(img)
win._timeline._bar.render(qp)
qp.end()
check("strip paints", True)
win._timeline._bar.clicked.emit(5)
pump()
check("click on the strip goes to that frame", wc.current_image == paths[5])
win._goto_image(str(plain_img))
pump()
check("timeline hidden on a plain image", win._timeline.isHidden())
proj2 = wc.project
proj2.settings.hotkeys["track_start"] = "Ctrl+Alt+T"
win._apply_hotkeys(proj2.settings.hotkeys)
check("track keys follow project hotkeys", win._act_track_start.shortcut().toString() == "Ctrl+Alt+T")
del proj2.settings.hotkeys["track_start"]

win._goto_image(paths[8])
pump()
win._activate_tool("bbox")
win._video.active_track = 3
win._track_keyframe()
pump()
check("Shift+T switches to Select, so the copy can be dragged at once",
      win._current_tool_name() == "select"
      and any(track_id(a) == 3 for a in wc.current_annotations))

from annotator.video.import_dialog import ImportVideoDialog
dlg = ImportVideoDialog(wc, win, path=str(VIDEO))
check("import dialog reads the video", dlg._run.isEnabled() and "160×120" in dlg._about.text())
check("default step about 5 frames per second", dlg._step.value() == 5)
check("estimate shown", "10" in dlg._estimate.text())
check("unique id for a second import", dlg._vid == "улица_1")
dlg._step.setValue(25)
before_n = len(wc.project.images)
dlg._start_extract()
check("import runs in the background", wait(lambda: dlg.result() == QDialog.DialogCode.Accepted, 30))
check("frames added, first frame known",
      len(wc.project.images) == before_n + 2 and dlg.first_frame.endswith("улица_1_000000.jpg"))
from annotator.ui.dialogs.split_dataset_dialog import SplitDatasetDialog
sd = SplitDatasetDialog(wc.project, win)
check("split dialog offers 'by video' when frames exist", not sd._video_cb.isHidden() and sd.by_video)
from annotator.ui.dialogs.project_settings_dialog import _HOTKEY_LABELS
check("track hotkeys listed in project settings",
      {"track_start", "track_keyframe", "track_prev_key", "track_next_key"}
      <= {k for k, _ in _HOTKEY_LABELS})
from annotator.ui.dialogs.export_dialog import _FORMATS
check("MOT in the export formats", "mot" in [k for _, k in _FORMATS])


# close every window: one left open is destroyed during interpreter shutdown,
# its app-wide key filter then crashes the process (random exit code 139)
from PyQt6.QtWidgets import QApplication as _QApp
for _w in _QApp.topLevelWidgets():
    _w.close()

print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
