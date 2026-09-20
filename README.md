# YOLO Annotator

A desktop image annotation tool for preparing training datasets for computer vision tasks — detection, segmentation, OBB, pose estimation, and classification.

## Features

- **8 annotation types**: bounding box, polygon, brush mask, OBB, keypoints/pose, polyline, point, classification
- **8 export formats**: YOLO Detect / Segment / OBB / Pose / Point / Classify, COCO Instances, COCO Keypoints
- **Multi-task export**: shared `images/`, separate label folders for parallel model training
- **Auto-export**: `labels/` updated automatically on every save — no manual export step needed
- **Dataset split**: train / val / test with configurable proportions and shuffle
- **QC validation**: detects empty images, duplicate annotations, tiny polygons — with one-click navigation to each issue
- **Annotation attributes**: custom fields per class (text, number, bool, select) → exported to COCO JSON
- **Multi-user mode**: shared network folder; leader assigns images to annotators via built-in dialog
- **Plugin system**: drop a `.py` file in `plugins/` — tool appears in the toolbar automatically
- **Full undo / redo** for all annotation operations

## Annotation Types

| Type             | Hotkey | Description                                      |
|------------------|--------|--------------------------------------------------|
| Bounding Box     | `B`    | Axis-aligned rectangle — object detection        |
| Polygon          | `P`    | Closed contour — instance segmentation           |
| Polyline         | `L`    | Open line — roads, cables, linear features       |
| OBB              | `O`    | Rotated bbox — aerial images, document detection |
| Keypoints / Pose | `K`    | Named skeleton points with edges                 |
| Point            | `.`    | Single centroid — counting, landmarks            |
| Classification   | —      | Image-level label with no geometry               |
| Brush mask       | `M`    | Pixel-painted binary mask → polygon on commit    |

## Export Formats

| Format           | Output                                      | Notes                                               |
|------------------|---------------------------------------------|-----------------------------------------------------|
| YOLO Detect      | `labels/*.txt`                              | `class cx cy w h` normalised                        |
| YOLO Segment     | `labels/*.txt`                              | polygon vertices; BBOX → 4-corner polygon (8 nums)  |
| YOLO OBB         | `labels/*.txt`                              | 4 corner points TL→TR→BR→BL                         |
| YOLO Pose        | `labels/*.txt`                              | bbox + keypoints `[x y v]`; `kpt_names` in data.yaml|
| YOLO Point       | `labels/*.txt`                              | 1-keypoint pose with 1% synthetic bbox              |
| YOLO Classify    | folder structure                            | `split/<class_name>/image.jpg`                      |
| COCO Instances   | `annotations/instances_<split>.json`        | bbox, segmentation, per-annotation attributes       |
| COCO Keypoints   | `annotations/keypoints_<split>.json`        | keypoints in pixels + skeleton edges in category    |

## Installation

```bat
cd new_annotator
install.bat        # creates .venv and installs dependencies (first time)
run.bat            # launch the annotator
```

Or manually:

```bat
cd new_annotator
.venv\Scripts\python main.py
```

**Requirements:** Python 3.13+ · Windows (PyQt6)

## Changelog

### v1.1
- **Subclass selector** — when annotating, a combobox appears in the Annotations panel to assign a subclass to any annotation (subclasses are defined per class in the Class Schema Editor)
- **Drag & drop images** — drag image files or folders directly onto the Images panel to add them to the project
- **Image filters** — search by filename, filter by split (train / val / test) and annotation status (All / Annotated / Unannotated); header shows `Images (N / total)` when a filter is active

### v1.0
- Initial release

## Tech Stack

- **UI**: PyQt6 ≥ 6.4
- **Geometry**: shapely ≥ 2.0 (buffering, IoU, area)
- **Image I/O**: Pillow ≥ 9.0, OpenCV 4.13
- **Runtime**: Python 3.13, fully offline — no cloud dependencies
- **Storage**: `.annproj/` directory — JSON metadata + PNG masks

## Project Structure

```
new_annotator/
├── annotator/
│   ├── domain/       ← data model  (Project, LabelClass, Annotation)
│   ├── storage/      ← project load/save
│   ├── exporters/    ← one module per export format
│   ├── tools/        ← annotation tools (base + built-in)
│   ├── ui/           ← PyQt6 widgets, panels, dialogs
│   └── controller/   ← ProjectController (MVC)
├── plugins/          ← custom tool plugins (*.py)
├── docs/             ← About.md, hotkeys.md, Test_Help.md
└── main.py
```
