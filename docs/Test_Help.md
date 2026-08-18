# Annotator — план ручного тестирования

> **Запуск:** `cd new_annotator && run.bat`  
> **Тестовые изображения:** любая папка с JPG/PNG файлами (минимум 3–5 шт.)

---

## 1. Проект

### Создание - Ок!!!
**Используем:** File → New Project (Ctrl+N)  
**Делаем:** указываем имя и папку → OK  
**Получаем:** заголовок окна меняется на имя проекта; в папке появляется `<name>.annproj/project.json` и `class_schema.json`, images.json, project.json

#### Замечания
1. Нужен ли чек-бокс Allowed type, если можно выбрать только один - выбирается при создании класса
2. Добавить функционал редактирования добавленного атрибута. Сейчас только добавление или удаление.
3. images.json - для чего? - Сделано!
4. project.json - для чего? - Сделано!
5. Добавить редактор настроек Проекта - project.json.
6. Добавить в меню пункт - Закрыть проект

### Открытие - Ок!!!
**Используем:** File → Open Project (Ctrl+O)  
**Делаем:** выбираем папку `.annproj`  
**Получаем:** проект загружается, Images Panel заполнена, статусбар показывает кол-во изображений

### Сохранение / Автосохранение
**Используем:** File → Save (Ctrl+S); автосохранение каждые 60 с  
**Делаем:** разметить что-нибудь → Ctrl+S  
**Получаем:** `annotations/<image_stem>.json` обновлён в папке проекта

---

## 2. Изображения

### Добавление - ОК!
**Используем:** File → Add Images from Folder  
**Делаем:** выбираем папку с JPG/PNG  
**Получаем:** Images Panel заполнена; каждое изображение с сплитом `train` по умолчанию 

#### Замечания
1. Что такое сплит train?


### Навигация  - ОК!
**Используем:** клик в Images Panel; клавиши A / D  
**Делаем:** переходим между изображениями  
**Получаем:** канвас перезагружается, Annotations Panel обновляется

### Сплиты (train/val/test)   - ОК!
**Используем:** ПКМ на изображении в Images Panel  
**Делаем:** выбираем `val` или `test`  
**Получаем:** иконка сплита меняется - меняется цвет и подпись!; при экспорте файл попадает в нужную подпапку

#### Замечания
1. Где иконка сплита?
---

## 3. Классы и схема

### Создание класса - ОК!
**Используем:** Schema → Edit Class Schema → + Add  
**Делаем:** вводим имя, выбираем annotation_type (bbox / polygon / polyline / obb / keypoints) → OK  
**Получаем:** класс появляется в Classes Panel с цветным маркером

### Изменение класса - ОК!
**Используем:** Schema → Edit Class Schema → выбираем класс  
**Делаем:** меняем имя, цвет, subclasses, display style → OK  
**Получаем:** изменения применяются; canvas перестраивает цвет аннотаций

### Скелет для keypoints-класса  - ОК!
**Используем:** Schema → Edit Class Schema → класс с типом keypoints  
**Делаем:**
1. "+ Add keypoint" × N (вводим имена: nose, left_eye, right_eye…)
2. В поле **Edges** вводим пары: `0-1, 0-2, 1-3` → Enter → OK

**Получаем:** скелет сохранён в `class_schema.json`:
```json
{
  "id": 0,
  "name": "person",
  "annotation_type": "keypoints",
  "skeleton": [
    {"name": "nose",      "edges": [1, 2]},
    {"name": "left_eye",  "edges": [0]},
    {"name": "right_eye", "edges": [0]}
  ]
}
```

#### Замечания
1. Добавить Стандартные наборы keypoints. Сохранение, загрузка, редактирование

### Удаление класса - ОК!
**Используем:** ПКМ на классе → Delete  
**Делаем:** выбираем "Delete annotations" или "Reassign to …"  
**Получаем:** класс удалён, аннотации удалены или переназначены
1. ПКМ на классе → Delet - нет такой функции. Может добавить или кнопку уделения.
2. Что такое "Reassign to …"

---

## 4. Инструменты разметки

### Select [V] +
**Используем:** тулбар ✦ Select / клавиша V  
**Делаем:** клик на аннотацию → выделяется; тащим угловой маркер → изменяем форму; Delete → удаляем  
**Получаем:** аннотация подсвечивается, Annotations Panel выделяет соответствующую строку; геометрия обновляется

### Polygon [P] +
**Используем:** выбрать класс типа `polygon`; тулбар ⬠ Polygon / клавиша P  
**Делаем:** кликаем вершины контура → при клике близко к первой точке замыкаем (или Enter / двойной клик); RMB = удалить последнюю точку; Esc = отмена  
**Получаем:** замкнутый полигон на канвасе; в Annotations Panel — тип SEGMENT

### Polyline [L] +
**Используем:** класс типа `polyline`; клавиша L  
**Делаем:** кликаем точки → Enter / двойной клик = зафиксировать; RMB = undo последней  
**Получаем:** открытая полилиния; тип POLYLINE

### BBox [B] +
**Используем:** класс типа `bbox`; клавиша B  
**Делаем:** зажимаем ЛКМ и тащим прямоугольник  
**Получаем:** ось-выровненный прямоугольник; тип BBOX; угловые маркеры для resize

### OBB [O] +
**Используем:** класс типа `obb`; клавиша O  
**Делаем:** зажимаем ЛКМ и тащим → отпускаем → тащим второй раз для поворота  
**Получаем:** повёрнутый прямоугольник; тип OBB; 4 угловых маркера

### Crack [C] +
**Используем:** класс типа `polygon`; клавиша C  
**Делаем:**
1. Кликаем вдоль трещины (полилиния); Enter / dbl-click = зафиксировать
2. Параметры в Tool Props Panel: **buffer_width** (ширина буфера), **cap_style**

**Получаем:** аннотация типа SEGMENT (буферизованный полигон); в Annotations Panel кнопка **Edit source** активна

### Crack — Edit source +
**Используем:** выделить crack-аннотацию → кнопка **Edit source** в Annotations Panel  
**Делаем:** добавляем / убираем точки исходной полилинии → Enter  
**Получаем:** полигон пересчитан с теми же параметрами буфера; Ctrl+Z отменяет

### Pose [K] +
**Используем:** класс типа `keypoints`; клавиша K  
**Делаем:**
- *Без скелета:* кликаем точки → Enter / dbl-click = commit; RMB = undo; Esc = cancel
- *Со скелетом N точек:* кликаем N точек → авто-commit; превью показывает имена и рёбра
- *Частично:* разместить < N точек → Enter → остальные добавляются как невидимые (v=0)

**Получаем:** аннотация POSE; в Annotations Panel — тип POSE

### Point [.]
**Используем:** класс любого типа; клавиша `.` (точка)  
**Делаем:** один клик ЛКМ → аннотация создаётся немедленно (Enter не нужен); Esc скрывает превью  
**Получаем:** одиночная точка (ghost-кружок 6 экр.пикс.); тип POINT в Annotations Panel

---

### Classify [кнопка]
**Используем:** создать класс типа `classification`; выбрать его в Classes Panel  
**Делаем:** в Annotations Panel появляется кнопка **`+ Classify as "<имя>"`** → нажать  
**Получаем:** IMAGE LABEL-аннотация для текущего изображения; повторный клик → предупреждение "Already labeled"

> Все drawing-инструменты при активном classification-классе блокируются автоматически.

---

### Brush / Mask [M]
**Используем:** класс любого типа; клавиша `M`  
**Делаем:**
1. Рисуем кистью: ЛКМ + drag → закрашиваем область
2. **Tool Props:** `Brush size` (px) и `Mode` (draw / erase)
3. Enter или double-click → commit → маска сохраняется
4. Esc → discard (без потери данных, см. Re-edit)

**Получаем:** аннотация типа MASK; в Annotations Panel отображается как MASK; PNG-файл сохраняется в `.annproj/masks/`

#### Re-edit маски
| Способ | Шаги |
|--------|------|
| Загрузить конкретную маску | Select → выделить нужную маску → нажать M → маска загружается в canvas |
| Авто-загрузка при стирании | M → Erase mode → первый мазок на пустом canvas → загружает последнюю маску текущего класса |

> **Esc при ре-едите** → оригинальная маска возвращается на место (данные не теряются).  
> Enter при ре-едите → старая маска заменяется новой.

---

## 5. Undo / Redo

**Используем:** Ctrl+Z / Ctrl+Shift+Z (или Edit → Undo / Redo)  
**Делаем:** рисуем несколько аннотаций → Ctrl+Z несколько раз  
**Получаем:** аннотации откатываются по одной; повтор Ctrl+Shift+Z возвращает

---

## 6. Валидация (QC)

**Используем:** QC → Validate Project (Ctrl+Shift+V); вкладка QC в правой панели  
**Делаем:** пометить хотя бы одно изображение без аннотаций; нарисовать очень маленький полигон; запустить валидацию  
**Получаем:** в QC Panel список issues:

| Тип | Описание |
|-----|----------|
| WARNING | Empty image — изображение без аннотаций |
| WARNING | Small polygon — площадь ниже порога |
| WARNING | Duplicate annotation — аннотации с одинаковой геометрией |

Клик по issue → переходим на нужное изображение, аннотация выделяется.

### Экспорт отчёта
**Используем:** QC → Export Report (JSON) / Export Report (CSV)  
**Получаем:**
```json
[
  {"image": "img1.jpg", "annotation_id": "...", "rule": "EmptyImage",
   "severity": "warning", "message": "No annotations on this image"}
]
```

---

## 7. Экспорты

### Общее
**Используем:** File → Export Dataset (Ctrl+E)  
**Делаем:** выбираем формат, выходную папку, флаг "Copy images" → Export  
**Получаем:**
```
<output>/
  images/
    train/   val/   test/
  labels/
    train/   val/   test/
  data.yaml          (для YOLO-форматов)
  annotations/       (для COCO)
```

---

### 7.0 Обзор: совместимость аннотаций и форматов

#### Какие типы экспортирует каждый формат

| Тип аннотации | Detect | Segment | OBB | Pose | Point | Classify |
|--------------|:------:|:-------:|:---:|:----:|:-----:|:--------:|
| **BBOX** | ✓ | ✓ → полигон | — | — | — | — |
| **POLYGON / SEGMENT** | ★ | ✓ | — | — | — | — |
| **POLYLINE** | ★ | ✓ | — | — | — | — |
| **MASK** | ★ | ✓ → контур | — | — | — | — |
| **OBB** | — | — | ✓ | — | — | — |
| **POSE (keypoints)** | — | — | — | ✓ | — | — |
| **POINT** | — | — | — | — | ✓ | — |
| **CLASSIFICATION** | — | — | — | — | — | ✓ |

★ — только при `geometry_policy = Convert`; при `Skip` (по умолчанию) — игнорируется.

#### Формат строки в label-файле

| Формат | Строка | Примечание |
|--------|--------|------------|
| **Detect** | `cls cx cy w h` | нормализованные [0, 1] |
| **Segment** | `cls x1 y1 x2 y2 … xn yn` | произвольное кол-во вершин |
| **OBB** | `cls x1 y1 x2 y2 x3 y3 x4 y4` | 4 угла TL→TR→BR→BL (8 чисел) |
| **Pose** | `cls cx cy w h  kx1 ky1 v1  kx2 ky2 v2 …` | v: 0=невидим, 2=виден; bbox авто из keypoints + 5% отступ |
| **Point** | `cls cx cy 0.01 0.01  x y 2` | 1-keypoint pose; синтетический bbox 1% |
| **Classify** | — (нет labels/) | папочная структура `<split>/<class_name>/img.jpg` |

#### Как Detect конвертирует чужие типы (Convert-policy)

| Тип | Результат |
|-----|-----------|
| POLYGON / SEGMENT | bounding box вершин → `cx cy w h` |
| POLYLINE | bounding box вершин → `cx cy w h` |
| MASK | bbox из метаданных (`ann.data["bbox"]`) → `cx cy w h` |

---

### 7.1 YOLO Detect +
**Формат:** `class_id  cx  cy  w  h` (нормализованные [0,1])

**Пример `labels/train/img1.txt`:**
```
0 0.512 0.342 0.234 0.156
1 0.720 0.510 0.180 0.210
```

**Пример `data.yaml`:**
```yaml
path: C:/dataset
train: images/train
val: images/val
nc: 2
names: ['car', 'person']
```

---

### 7.2 YOLO Segment +
**Формат:** `class_id  x1 y1  x2 y2  ...  xn yn`

**Пример `labels/train/img1.txt`:**
```
0 0.234 0.156 0.456 0.134 0.678 0.156 0.580 0.310 0.234 0.310
```
> **BBOX** → конвертируется в полигон из 4 угловых точек TL→TR→BR→BL: итого **8 чисел**.  
> **MASK** → экспортируется как контур маски (полигон из `ann.data["polygon"]`).  
> **POLYLINE** → экспортируется как есть (вершины полилинии).  
> **OBB / POSE / POINT / CLASSIFY** — игнорируются.

---

### 7.3 YOLO OBB +
**Формат:** `class_id  x1 y1  x2 y2  x3 y3  x4 y4` (4 угла повёрнутого прямоугольника)

**Пример `labels/train/img1.txt`:**
```
0 0.234 0.156 0.456 0.134 0.480 0.290 0.258 0.312
```

---

### 7.4 YOLO Pose
**Формат:** `class_id  cx cy w h  kx1 ky1 v1  kx2 ky2 v2  ...`  
`v`: 0 = не размечена, 2 = видима  
bbox = авто-вычисляется из видимых точек + 5% отступ

**Пример `labels/train/img1.txt` (3 keypoints):**
```
0 0.512 0.342 0.180 0.210 0.500 0.290 2 0.480 0.310 2 0.530 0.308 2
```

**Пример `data.yaml` (с kpt_shape):**
```yaml
path: C:/dataset
train: images/train
val: images/val
nc: 1
names: ['person']

kpt_shape: [3, 3]
```

---

### 7.5 COCO Instances
**Формат:** JSON per split; атрибуты включены; bbox в пикселях `[x, y, w, h]`

**Пример `annotations/instances_train.json`:**
```json
{
  "info": {"version": "1.0", "description": "Exported by Annotator"},
  "licenses": [],
  "categories": [
    {"id": 0, "name": "car",    "supercategory": ""},
    {"id": 1, "name": "person", "supercategory": ""}
  ],
  "images": [
    {"id": 1, "file_name": "img1.jpg", "width": 1920, "height": 1080}
  ],
  "annotations": [
    {
      "id": 1,
      "image_id": 1,
      "category_id": 0,
      "segmentation": [[234, 168, 438, 144, 652, 168, 558, 334, 225, 334]],
      "bbox": [225, 144, 427, 190],
      "area": 38430,
      "iscrowd": 0,
      "attributes": {"damage": "heavy"}
    }
  ]
}
```

> Атрибуты класса (если заданы) попадают в поле `"attributes": {...}` каждой аннотации.

---

### 7.6 COCO Keypoints
**Формат:** JSON per split; keypoints в пикселях `[x y v  x y v  ...]`  
`v`: 0 = отсутствует, 2 = видима  
bbox авто-вычисляется из видимых точек + 5% от размера изображения

**Пример `annotations/keypoints_train.json`:**
```json
{
  "categories": [
    {
      "id": 4,
      "name": "person",
      "supercategory": "",
      "keypoints": ["nose", "left_eye", "right_eye"],
      "skeleton": [[0, 1], [0, 2]]
    }
  ],
  "images": [
    {"id": 0, "file_name": "img1.jpg", "width": 1920, "height": 1080}
  ],
  "annotations": [
    {
      "id": 0,
      "image_id": 0,
      "category_id": 4,
      "keypoints": [487.07, 530.17, 2, 387.93, 729.88, 2, 574.35, 731.32, 2],
      "num_keypoints": 3,
      "bbox": [291.93, 476.17, 378.42, 309.71],
      "area": 116978.0,
      "iscrowd": 0
    }
  ]
}
```

> Экспортирует только POSE-аннотации; остальные типы игнорируются.  
> `skeleton` в категории — рёбра 0-indexed, как в схеме классов.  
> Если точка не размечена (v=0), координаты `x=0 y=0`.

---

### 7.8 YOLO Point
**Формат:** YOLO 1-keypoint pose с синтетическим bbox 1%  
`class_id  cx cy 0.01 0.01  x y 2`

**Пример `labels/train/img1.txt`:**
```
0 0.512 0.342 0.010 0.010 0.512 0.342 2
```

**Пример `data.yaml`:**
```yaml
nc: 1
names: ['crack_center']
kpt_shape: [1, 3]
```

---

### 7.9 YOLO Classify
**Структура:** папочная — изображение копируется в `<split>/<class_name>/`

```
output/
  train/
    cat/
      img1.jpg
    dog/
      img2.jpg
  val/
    cat/
      img4.jpg
```

> Нет `labels/` и `data.yaml` — это стандартный формат для `torchvision.datasets.ImageFolder`.

---

### 7.10 Multi-task (общий images/, несколько форматов)

**Используем:** File → Export Dataset → режим **Multi-task**  
**Выбираем:** любую комбинацию чекбоксов; политику несовместимых типов  
**Получаем** (при всех 5 чекбоксах):
```
<output>/
  images/
    train/   val/              ← изображения скопированы один раз (для detect/seg/obb/pose)
  labels_detect/
    train/   val/              ← bbox-файлы
  labels_segment/
    train/   val/              ← polygon-файлы
  labels_obb/
    train/   val/              ← OBB-файлы (4 угла)
  labels_pose/
    train/   val/              ← keypoint-файлы
  classify/
    train/
      <class_name>/            ← изображения для classify (свои копии)
    val/
      <class_name>/
  data_detect.yaml
  data_segment.yaml
  data_obb.yaml
  data_pose.yaml               ← включает kpt_shape
```

> **Classify** выгружается в отдельную папку `classify/` — у него другая структура (папки по классам вместо labels/*.txt), поэтому `images/` он не использует.

**Пример `data_detect.yaml`:**
```yaml
# Multi-task export — images shared at images/{split}/
# Labels at labels_detect/{split}/
path: C:/exports/run1
train: images/train
val: images/val
label_dir: labels_detect
nc: 2
names: ['car', 'person']
```

**Пример `data_pose.yaml`** (с kpt_shape):
```yaml
# Multi-task export — images shared at images/{split}/
# Labels at labels_pose/{split}/
path: C:/exports/run1
train: images/train
val: images/val
label_dir: labels_pose
nc: 1
names: ['person']
kpt_shape: [3, 3]
```

#### Доступные чекбоксы в Multi-task

| Чекбокс | Папка с лейблами | yaml-файл | Примечание |
|---------|-----------------|-----------|------------|
| YOLO Detect | `labels_detect/` | `data_detect.yaml` | affected by geometry_policy |
| YOLO Segment | `labels_segment/` | `data_segment.yaml` | — |
| YOLO OBB | `labels_obb/` | `data_obb.yaml` | только OBB-аннотации |
| YOLO Pose | `labels_pose/` | `data_pose.yaml` | + kpt_shape в yaml |
| YOLO Classify | `classify/` | нет yaml | отдельная папочная структура |

#### Политика несовместимых типов (`geometry_policy`)

| Политика | Поведение при YOLO Detect |
|----------|--------------------------|
| **Skip** (по умолчанию) | Экспортирует только BBOX-аннотации; MASK/POLYGON/OBB/POSE игнорируются |
| **Convert** | BBOX → как обычно; MASK → bbox из `ann.data["bbox"]`; POLYGON → bounding box из вершин |

> Для Segment, OBB, Pose и Classify политика не влияет — каждый экспортёр обрабатывает только свой тип.

---

## 8. Схема классов — импорт / экспорт

### Экспорт
**Используем:** Schema → Export class_schema.json  
**Получаем:** файл с полной схемой включая skeleton, attributes, display_style

### Импорт
**Используем:** Schema → Import class_schema.json  
**Делаем:** выбираем JSON с другого проекта  
**Получаем:** диалог конфликтов (если имена или ID совпадают); выбираем "Keep existing" / "Replace" / "Add as new"

---

## 9. Плагины

**Используем:** папка `new_annotator/plugins/`  
**Делаем:** добавить `.py` файл с классом-наследником `BaseTool` → перезапустить приложение  
**Получаем:** Tools → Plugin: <name> появляется в меню

**Проверка встроенного примера:**  
`plugins/example_tool.py` уже присутствует → Tools → Plugin: example_stamp → инструмент активируется (ничего не рисует — заглушка)

---

## 10. Быстрая смоук-сессия (15 мин)

| # | Действие | Ожидание |
|---|----------|----------|
| 1 | New Project → Add Images (5 фото) | 5 строк в Images Panel |
| 2 | Create class "defect" / polygon | класс в Classes Panel |
| 3 | Polygon [P]: разметить 2 полигона на img1 | 2 аннотации в Annotations Panel |
| 4 | BBox [B]: разметить 1 bbox | 3 аннотации |
| 5 | Crack [C]: нарисовать трещину, изменить buffer_width | полигон-буфер пересчитывается |
| 6 | Crack → Edit source → добавить точку → Enter | полигон обновлён |
| 7 | Create class "person" / keypoints, скелет 3 точки | skeleton в schema |
| 8 | Pose [K]: разместить 3 точки на img2 | авто-commit, рёбра видны |
| 9 | Point [.]: кликнуть точку на img3 | аннотация POINT создаётся немедленно |
| 10 | Brush [M]: нарисовать маску → Enter | аннотация MASK в панели, PNG в masks/ |
| 11 | Select → выделить маску → M → Esc | маска возвращается на место (не теряется) |
| 12 | Ctrl+Z × 3 | аннотации откатываются |
| 13 | ПКМ на img4 → val | иконка сплита меняется |
| 14 | QC → Validate | список issues |
| 15 | Export → Single → YOLO Pose | `labels/train/*.txt` + `kpt_shape` в yaml |
| 16 | Export → Multi-task → Detect + Segment | `labels_detect/` + `labels_segment/` + shared `images/` |
| 17 | Export → Multi-task → OBB | `labels_obb/train/*.txt` + `data_obb.yaml` |
| 18 | Export → Multi-task → Pose | `labels_pose/train/*.txt` + `kpt_shape` в `data_pose.yaml` |
| 19 | Export → Multi-task → Classify | `classify/train/<class>/img.jpg` (без labels/) |
| 20 | Export → Multi-task → Detect (Convert) + Segment | POLYGON → bbox в `labels_detect/`; polygon → `labels_segment/` |
| 21 | Ctrl+S | сохранено без ошибок |
