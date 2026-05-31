# YOLO Annotator

A desktop image annotation tool built with PyQt6. Supports bounding boxes, polygons, polylines, OBB, keypoints, points, classification, and brush-painted segmentation masks.

## Project structure

```
new_annotator/   — main application (Python 3.13, PyQt6)
docs/            — architecture notes, roadmap, phase completion reports
Archive/         — legacy prototypes (reference only)
```

## Quick start

```bat
cd new_annotator
install.bat          # create .venv and install dependencies (first time only)
run.bat              # launch the annotator
```

Or manually:

```bat
cd new_annotator
.venv\Scripts\python main.py
```

## Requirements

- Python 3.13+
- See `new_annotator/requirements.txt` for full dependency list

## Annotation types

| Type           | Hotkey | Export format        |
|----------------|--------|----------------------|
| Bounding box   | B      | YOLO detect          |
| Polygon        | P      | YOLO segment         |
| Polyline       | L      | —                    |
| OBB            | O      | YOLO OBB             |
| Keypoints/Pose | K      | YOLO pose            |
| Point          | .      | YOLO detect (1px)    |
| Classification | C      | YOLO classify        |
| Brush mask     | M      | YOLO segment         |
