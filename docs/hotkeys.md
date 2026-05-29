# Default Hotkeys

Based on CVAT standard layout with additional shortcuts for infrastructure annotation workflows.

---

## General

| Hotkey | Action |
|---|---|
| `Ctrl+S` | Save project |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Ctrl+Y` | Redo (alternative) |
| `F1` | Show hotkey reference |
| `F2` | Open settings |
| `Esc` | Cancel current action / exit current mode |

---

## Image Navigation

| Hotkey | Action |
|---|---|
| `D` | Previous image |
| `F` | Next image |
| `A` | Previous image (alternative) |
| `C` | Back N frames (step size configurable in settings) |
| `V` | Forward N frames (step size configurable in settings) |
| `←` | Previous image with annotations |
| `→` | Next image with annotations |

---

## Drawing Tools

| Hotkey | Action |
|---|---|
| `Shift+B` | Activate BBox tool |
| `Shift+P` | Activate Polygon tool |
| `Shift+L` | Activate Polyline tool |
| `Shift+O` | Activate OBB tool |
| `Shift+K` | Activate Keypoints tool |
| `N` | Repeat last draw action (same class, same tool) |
| `1`–`9` | Quick class select by index |
| `[` | Previous class |
| `]` | Next class |
| `Q` | Activate last used custom tool (e.g. Crack Tool) |

---

## Drawing Polygon / Polyline

| Hotkey | Action |
|---|---|
| `Click` | Add vertex |
| `Right Click` / `RMB` | Undo last vertex |
| `Enter` | Finish drawing |
| `Double Click` | Finish drawing (alternative) |
| `Esc` | Cancel drawing entirely |
| `Ctrl` (hold) | Snapping / magnetic mode |
| `Alt+Click` on vertex | Delete vertex |

---

## Object Management

| Hotkey | Action |
|---|---|
| `Del` | Delete selected object |
| `Ctrl+D` | Duplicate selected object |
| `Tab` | Select next object |
| `Shift+Tab` | Select previous object |
| `L` | Lock / unlock selected object |
| `T+L` | Lock / unlock all objects |
| `H` | Hide / show selected object |
| `T+H` | Hide / show all objects |
| `X` | Toggle visibility of all annotations (preview clean image) |

---

## Group / Merge / Split

| Hotkey | Action |
|---|---|
| `G` | Group selected objects |
| `Shift+G` | Ungroup selected objects |
| `M` | Merge objects mode |
| `Alt+M` | Split object mode |

---

## Canvas / Viewport

| Hotkey | Action |
|---|---|
| `Space` | Fit image to screen |
| `F` | Fit image to screen (alternative) |
| `Scroll wheel` | Zoom in / out |
| `Middle Mouse Button` (hold) | Pan |
| `Shift+Scroll` | Horizontal scroll |
| `Ctrl+R` | Rotate image +90° |
| `Ctrl+Shift+R` | Rotate image −90° |

---

## Project & Settings

| Hotkey | Action |
|---|---|
| `Ctrl+N` | New project |
| `Ctrl+O` | Open project |
| `Ctrl+E` | Export current project |
| `Ctrl+,` | Open Project Settings / Class Schema Editor |

---

## Implementation Notes

- All hotkeys must be configurable in Project Settings.
- Custom tool hotkeys (e.g. Crack Tool) must be assignable per tool manifest.
- Hotkey configuration must be stored in `project.json` and portable with project settings export.
- Class quick-select keys `1`–`9` map to class index in the current project schema.
- `N` (repeat last draw) must remember: last active tool + last active class.
- `T+L` and `T+H` are sequential key presses, not simultaneous.
- Show a hotkey reference overlay on `F1` — rendered from the current hotkey config, not hardcoded.
