# Отчёт о завершении Фазы 5

## Итог

Фаза 5 реализует полный слой экспорта датасетов: OBB инструмент с canvas-item,
три YOLO-экспортёра (detect / segment / obb), разбивку датасета на сплиты
(train / val / test), генерацию `data.yaml` и диалог экспорта в главном окне.

---

## Что реализовано

### Блок 1 — OBB инструмент

**`annotator/tools/obb_tool.py`**

| Поведение | Описание |
|-----------|----------|
| Рисование | Drag мышью — создаёт OBB с `angle_deg=0` (горячая клавиша **O**) |
| Данные | `{cx, cy, w, h, angle_deg}` в нормализованных координатах |
| Preview | Оранжевая пунктирная рамка во время drag |
| Отмена | Escape — сбрасывает текущий drag |

Инструмент зарегистрирован в `ANNOTATION_TYPE_DEFAULT_TOOL["obb"] = "obb"` —
при выборе класса с типом `obb` тулбар автоматически переключается на OBB-инструмент.

---

### Блок 2 — OBB canvas item

**`annotator/ui/canvas/items/obb_item.py`**

Класс `OBBAnnotationItem` — отрисовка повёрнутого прямоугольника с полным набором ручек:

| Handle | Индекс | Визуал | Действие |
|--------|--------|--------|----------|
| Вращение | 0 | оранжевый кружок выше верхней грани | поворот по часовой стрелке |
| Угол TL | 1 | белый кружок | resize, фиксируя угол BR |
| Угол TR | 2 | белый кружок | resize, фиксируя угол BL |
| Угол BR | 3 | белый кружок | resize, фиксируя угол TL |
| Угол BL | 4 | белый кружок | resize, фиксируя угол TR |

**Математика угла (rotate):**

Угол откладывается по часовой стрелке в экранных координатах (Y-ось вниз):
```
angle = degrees(atan2(dx, -dy))   # dx, dy — от центра до курсора
```

**Математика resize угловой ручки:**

При перетаскивании угла `i`:
1. Противоположный угол `(i+2) % 4` зафиксирован в экранных координатах.
2. Новый центр = midpoint(новый угол, фиксированный угол).
3. Смещение в OBB-локальных координатах (обратный поворот на -angle):
   ```
   dx_local = cos(θ)·dx + sin(θ)·dy
   dy_local = −sin(θ)·dx + cos(θ)·dy
   ```
4. `new_w = 2 · |dx_local|`,  `new_h = 2 · |dy_local|`

**Методы интерфейса BaseAnnotationItem:**
- `to_data(image_size)` → нормализованный dict `{cx, cy, w, h, angle_deg}`
- `update_from_data(data, image_size)` → обновление из нормализованных данных

Работает со стандартным `SelectTool` без изменений — через `handle_at` / `move_handle`.

---

### Блок 3 — Экспортёры

#### `annotator/exporters/base.py` — общий helper

```python
write_yolo_dataset(project, all_annotations, output_dir,
                   ann_to_line_fn, copy_images=True)
```

Пишет структуру:
```
output_dir/
  labels/{split}/img.txt     — по одному файлу на изображение
  images/{split}/img.jpg     — если copy_images=True
  data.yaml                  — пути, nc, names
```

`_write_data_yaml(project, output_dir)` — генерирует `data.yaml`:
```yaml
path: /absolute/path/to/output_dir
train: images/train
val: images/val      # только если есть изображения с split=val
test: images/test    # только если есть изображения с split=test
nc: 3
names: ['car', 'road', 'crack']
```

#### `annotator/exporters/yolo_detect.py`

| Параметр | Значение |
|----------|----------|
| Формат строки | `class_id cx cy w h` (нормализованные) |
| Типы | Только `BBOX` |
| cx, cy | `x + w/2`, `y + h/2` (конвертация из top-left в центр) |

#### `annotator/exporters/yolo_seg.py` (дополнен)

Метод `export()` теперь реализован через `write_yolo_dataset`.

| Параметр | Значение |
|----------|----------|
| Формат строки | `class_id x1 y1 x2 y2 … xn yn` |
| Типы | `SEGMENT`, `POLYLINE` (полигоны), `BBOX` (4-угольный полигон) |

Авто-экспорт на flush не изменился — работает как в Phase 2.

#### `annotator/exporters/yolo_obb.py`

| Параметр | Значение |
|----------|----------|
| Формат строки | `class_id x1 y1 x2 y2 x3 y3 x4 y4` (4 повёрнутых угла) |
| Порядок углов | TL → TR → BR → BL |
| Стандарт | ultralytics YOLO OBB |
| Типы | Только `OBB` |

Углы вычисляются из `{cx, cy, w, h, angle_deg}` через функцию поворота:
```
x' = cx + cos(θ)·dx − sin(θ)·dy
y' = cy + sin(θ)·dx + cos(θ)·dy
```

---

### Блок 4 — Split UI в Images Panel

**`annotator/ui/panels/images_panel.py`** (расширен):

| Изменение | Описание |
|-----------|----------|
| ПКМ на изображении | Контекстное меню: Set split: train / val / test |
| Метка в списке | `img.jpg [val]` или `img.jpg [test]` (train — без метки) |
| Цвет | train=дефолт, val=синий, test=оранжевый |
| Сигнал `split_changed` | Подключён к `ctrl.save_project()` — сохраняется немедленно |

Поле `ImageRecord.split` существовало с Phase 1 (default=`"train"`).

---

### Блок 5 — Export Dialog

**`annotator/ui/dialogs/export_dialog.py`** — класс `ExportDatasetDialog`:

- Поле **Format** — выпадающий список:
  - `YOLO Detect  (bbox → cx cy w h)`
  - `YOLO Segment  (polygon / polyline)`
  - `YOLO OBB  (oriented bbox → 4 corners)`
- Поле **Output folder** + кнопка Browse…
- Флажок **Copy images to output folder** (по умолчанию включён)
- **Сводка проекта** (read-only): количество изображений по сплитам, аннотации по типам

Свойства для Main Window: `format_name`, `output_dir`, `copy_images`.

---

### Блок 6 — Controller

**`annotator/controller/project_controller.py`** — два новых метода:

| Метод | Описание |
|-------|----------|
| `export_dataset(output_dir, format_name, copy_images)` | Flush текущего изображения → overlay in-memory → вызов нужного экспортёра |
| `get_annotation_type_counts()` | `{type_str: count}` по всему датасету (для сводки в диалоге) |

Поддерживаемые `format_name`: `"yolo_detect"`, `"yolo_seg"`, `"yolo_obb"`.

---

### Блок 7 — Main Window

**`annotator/ui/main_window.py`** (изменения):

| Добавлено | Описание |
|-----------|----------|
| `OBBTool` [O] | В тулбаре и меню Tools |
| `File › Export Dataset… [Ctrl+E]` | Открывает `ExportDatasetDialog` |
| `split_changed` → `save_project` | Изменение сплита сразу сохраняется |
| `ANNOTATION_TYPE_DEFAULT_TOOL["obb"] = "obb"` | Auto-switch при выборе OBB-класса |

---

## Файлы Фазы 5

```
annotator/
  tools/
    obb_tool.py              (OBBTool — drag рисование, горячая клавиша O)
  ui/
    canvas/
      items/
        obb_item.py          (OBBAnnotationItem — 5 handles: вращение + 4 угла)
      scene.py               (+ _make_item для AnnotationType.OBB)
    dialogs/
      export_dialog.py       (ExportDatasetDialog)
    panels/
      images_panel.py        (+ split_changed, context menu, цветовые метки)
    main_window.py           (+ OBBTool, Export Dataset меню)
  exporters/
    base.py                  (+ write_yolo_dataset, _write_data_yaml)
    yolo_detect.py           (новый — YOLO detect)
    yolo_obb.py              (новый — YOLO OBB)
    yolo_seg.py              (+ реализован метод export())
  controller/
    project_controller.py   (+ export_dataset, get_annotation_type_counts)
  domain/
    label_class.py           (ANNOTATION_TYPE_DEFAULT_TOOL["obb"] = "obb")

test_phase5.py               (74/74 checks)
docs/
  phase5_completion_ru.md
```

---

## Команды запуска

```bat
cd new_annotator
run.bat                              :: запуск приложения
.venv\Scripts\python test_phase1.py  :: регрессия Фаз 1–3 (35/35)
.venv\Scripts\python test_phase4.py  :: регрессия Фазы 4 (29/29)
.venv\Scripts\python test_phase5.py  :: тесты Фазы 5 (74/74)
```

---

## Шаги ручного тестирования

### 1. OBB инструмент
1. Открыть проект, создать класс с `annotation_type: obb`
2. Выбрать класс в панели — тулбар должен автоматически переключиться на **⬡ OBB**
3. Drag на холсте → появляется OBB с `angle_deg=0`
4. Выбрать OBB инструментом Select → должны появиться 5 ручек
5. Тянуть оранжевый кружок (ручка 0) → OBB вращается
6. Тянуть белый угловой кружок → OBB масштабируется вдоль своих осей

### 2. Split
1. ПКМ на любом изображении в панели Images
2. Меню: Set split → val
3. Имя изображения получает метку `[val]` синего цвета
4. Изменение сохраняется автоматически (status bar: "Saved: …")

### 3. Export Dataset
1. Меню **File → Export Dataset…** или `Ctrl+E`
2. Выбрать формат "YOLO Detect"
3. Выбрать пустую папку через Browse
4. Нажать Export
5. Проверить в папке: `labels/train/*.txt`, `images/train/*.jpg`, `data.yaml`
6. Открыть `data.yaml` — убедиться в наличии `nc` и `names`
7. Открыть один `.txt` — формат `class_id cx cy w h`

### 4. YOLO OBB export
1. Нарисовать несколько OBB с разными углами
2. **File → Export Dataset…** → формат "YOLO OBB" → Export
3. Открыть `.txt` — 9 полей: `class_id x1 y1 x2 y2 x3 y3 x4 y4`
4. Убедиться, что bbox и polygon аннотации пропущены (файл пуст или содержит только OBB)

### 5. YOLO Segment full export
1. Нарисовать polygon + polyline + bbox аннотации
2. Export → "YOLO Segment"
3. Каждая аннотация в файле: `class_id x1 y1 … xn yn`
4. Bbox конвертируется в 4-угольник (9 полей в строке)

---

## Критерии приёмки

| Критерий | Статус |
|----------|--------|
| OBB рисуется drag'ом | ✅ |
| OBB вращается за оранжевую ручку | ✅ |
| OBB масштабируется за угловые ручки | ✅ |
| Авто-переключение на OBB при выборе obb-класса | ✅ |
| YOLO detect: правильный формат cx cy w h | ✅ |
| YOLO seg: full project export работает | ✅ |
| YOLO obb: 4 повёрнутых угла в нормализованных координатах | ✅ |
| data.yaml генерируется с nc + names + split-путями | ✅ |
| Split меняется через ПКМ и сохраняется | ✅ |
| Export dialog показывает сводку датасета | ✅ |
| Регрессия Фаз 1–3: 35/35 | ✅ |
| Регрессия Фазы 4: 29/29 | ✅ |
| Тесты Фазы 5: 74/74 | ✅ |

---

## Известные ограничения

- **OBB вращение около граней изображения** — SelectTool зажимает позицию курсора в пределах изображения, поэтому ручка вращения немного ограничена у края. Решение: в будущей версии не зажимать для handle 0.
- **Нет body drag для OBB** — как и для bbox/polygon, переместить всю аннотацию без перетаскивания ручки нельзя. Требует отдельного центрального handle или режима перемещения в SelectTool.
- **copy_images=False** — изображения не копируются, data.yaml содержит относительные пути `images/{split}/`. Пользователь должен скопировать изображения вручную или использовать флаг копирования.
- **POSE и CLASSIFY** — инструменты и экспорт не реализованы (Phase 7).

---

## Предложение для Фазы 6 — Crack Tool / Plugin API

Перед реализацией требуется обсуждение архитектуры:

| Вопрос | Варианты |
|--------|---------|
| Где хранить исходную полилинию? | В `ann.data["source_polyline"]` — просто; или как отдельная связанная аннотация — чисто |
| Плагин или встроенный инструмент? | Crack Tool как встроенный (Phase 6); полноценный plugin API с папкой plugins/ — позже |
| UI параметров (ширина буфера)? | Боковая панель свойств инструмента или поле в тулбаре |
| tool_constraints в схеме класса? | Добавить `tool_constraints` dict в LabelClass при реализации plugin API |
