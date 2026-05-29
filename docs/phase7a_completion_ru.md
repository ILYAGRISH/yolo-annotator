# Отчёт о завершении Фазы 7A

## Итог

Фаза 7A реализует три блока:
1. **Skeleton schema** — определение скелета ключевых точек в схеме класса
2. **PoseTool [K]** — инструмент расстановки ключевых точек на канвасе
3. **YOLO Pose экспорт** — экспортёр в формат YOLO Pose

---

## Блок 1 — Skeleton schema в LabelClass

**`annotator/domain/label_class.py`**

### Новый датакласс `SkeletonKeypoint`

```python
@dataclass
class SkeletonKeypoint:
    name: str
    edges: list[int] = field(default_factory=list)  # индексы смежных точек
```

- Сериализуется через `to_dict` / `from_dict`
- Хранится в `class_schema.json` как часть класса

### Поле `skeleton` в `LabelClass`

```python
skeleton: list[SkeletonKeypoint] = field(default_factory=list)
```

- Присутствует во всех классах (пустой список для не-keypoints типов)
- Round-trip через `to_dict` → `from_dict` полный
- `ANNOTATION_TYPE_DEFAULT_TOOL["keypoints"]` = `"pose"` (было `None`)

### Редактор скелета в Class Schema Editor

**`annotator/ui/dialogs/class_schema_editor.py`**

- Группа "Skeleton" видна только при `annotation_type == "keypoints"`
- Список имён ключевых точек с кнопками "+ Add keypoint" / "− Remove last"
- Поле рёбер: строка вида `"0-1, 1-2, 1-5"` (пары индексов через запятую)
- Парсинг: дубликаты и self-loops игнорируются; out-of-range индексы отсекаются
- Удаление последней точки автоматически чистит все рёбра, ссылающиеся на неё

---

## Блок 2 — PoseTool [K]

**`annotator/tools/pose_tool.py`**

### Workflow

| Действие | Эффект |
|----------|--------|
| Левый клик | Разместить следующую ключевую точку (v=2, видима) |
| Правый клик | Удалить последнюю точку |
| Enter / двойной клик | Зафиксировать аннотацию |
| Escape | Отменить без сохранения |

### Два режима

**Свободный режим** (у класса нет скелета):
- Любое количество точек, фиксация по Enter / dbl-click

**Скелет-направляемый режим** (у класса есть skeleton):
- Авто-коммит при расстановке всех N точек из скелета
- Если Enter нажат до N — неразмещённые точки дополняются как невидимые (v=0)
- Если размещено больше N — лишние отсекаются

### Preview на канвасе

- Зелёные кружки на размещённых точках
- Имя точки из скелета рядом с кружком
- Рёбра скелета между уже размещёнными точками
- Полупрозрачный кружок-призрак у курсора для следующей точки

### Формат данных аннотации

```json
{"keypoints": [[x, y, v], ...]}
```

- `x`, `y` — нормализованные координаты [0, 1]
- `v` — видимость: `2` = видима, `0` = невидима (placeholder)

---

## Блок 3 — PoseAnnotationItem

**`annotator/ui/canvas/items/pose_item.py`**

- Ключевые точки: закрашенные кружки, белый контур, рядом — номер
- Рёбра скелета: линии между видимыми точками (v > 0)
- Невидимые точки (v=0) не отображаются и не рисуются линии к ним
- Цвет берётся из класса; при выделении — alpha и толщина линий увеличиваются
- `update_from_data` / `to_data` — стандартный интерфейс BaseAnnotationItem
- `boundingRect` — по видимым точкам с отступом; при отсутствии видимых → (0,0,1,1)
- Рёбра скелета передаются при создании из `scene._make_item` — берутся из `cls.skeleton`

---

## Блок 4 — YoloPoseExporter

**`annotator/exporters/yolo_pose.py`**

### Формат строки

```
class_id  cx cy w h  kx1 ky1 v1  kx2 ky2 v2  ...
```

- Все координаты нормализованы [0, 1]
- `cx cy w h` — авто-вычисляется из видимых точек + 5% отступ (clamped to [0,1])
- Аннотации без видимых точек пропускаются (возвращает None)

### Скелет-паддинг

| Ситуация | Поведение |
|----------|-----------|
| У класса есть skeleton (N точек) | Обрезать/дополнить до N |
| У класса нет skeleton | Экспортировать как есть |
| Дополнение | Invisible keypoints: `0.0 0.0 0` |

### data.yaml

Стандартный YOLO-yaml + дополнительная строка:
```yaml
kpt_shape: [N, 3]
```
где N = количество точек в скелете первого keypoints-класса. Добавляется путём append к уже записанному файлу (без изменения `base.py`).

### Интеграция

- `ExportDatasetDialog`: добавлен пункт "YOLO Pose (keypoints → bbox + kpoints)"
- `ProjectController.export_dataset`: ветка `format_name == "yolo_pose"`

---

## Wiring в main_window

**`annotator/ui/main_window.py`**

| Изменение | Описание |
|-----------|----------|
| `_build_tools` | `"pose": PoseTool()` |
| `_setup_toolbar` | Кнопка `✿ Pose [K]` в тулбаре (QActionGroup, checkable) |
| `_setup_menu` | `"Pose [K]"` в меню Tools с шорткатом K |
| `_tool_act_map` | `"pose": self._act_pose` |
| `_on_class_selected` | Перезагружает скелет в PoseTool при смене класса |
| toolbar hint | Добавлено "Pose" в подсказку инструментов |

---

## Файлы Phase 7A

```
annotator/
  domain/
    label_class.py              (+ SkeletonKeypoint, skeleton field, DEFAULT_TOOL)
  tools/
    pose_tool.py                (новый — PoseTool [K])
  ui/
    canvas/
      items/
        pose_item.py            (новый — PoseAnnotationItem)
      scene.py                  (+ POSE в _make_item)
    dialogs/
      class_schema_editor.py    (+ Skeleton GroupBox)
      export_dialog.py          (+ YOLO Pose в _FORMATS)
    main_window.py              (+ PoseTool, Pose [K] кнопка)
  exporters/
    yolo_pose.py                (новый — YoloPoseExporter)
  controller/
    project_controller.py       (+ ветка "yolo_pose")

new_annotator/
  test_phase7a.py               (новый — 109/109 checks)

docs/
  phase7a_completion_ru.md
```

---

## Команды запуска

```bat
cd new_annotator
run.bat                                         :: запуск приложения
.venv\Scripts\python test_phase7a.py           :: тесты Phase 7A (109/109)
.venv\Scripts\python test_phase1.py            :: регрессия Phase 1-3 (35/35)
.venv\Scripts\python test_phase4.py            :: регрессия Phase 4 (29/29)
.venv\Scripts\python test_phase5.py            :: регрессия Phase 5 (74/74)
.venv\Scripts\python test_phase6.py            :: регрессия Phase 6 (58/58)
.venv\Scripts\python test_phase7.py            :: регрессия Phase 7C (79/79)
```

---

## Шаги ручного тестирования

### 1. Создание класса с скелетом

1. **Schema → Edit Class Schema → + Add → "person", keypoints**
2. В правой панели появляется группа "Skeleton"
3. "+ Add keypoint" → "nose", "+ Add keypoint" → "left_eye", "+ Add keypoint" → "right_eye"
4. В поле Edges ввести: `0-1, 0-2` → Enter
5. OK → сохранено в class_schema.json

### 2. Разметка pose-аннотации

1. Выбрать класс "person" в Classes Panel
2. Тулбар автоматически переключается на PoseTool [K]
3. Кликнуть на нос → зелёный кружок с подписью "nose"
4. Кликнуть на левый глаз → появляется ребро nose–left_eye
5. Кликнуть на правый глаз → аннотация авто-зафиксирована (3 из 3)
6. В Annotations Panel видна аннотация типа POSE

### 3. Частичная аннотация

1. Разместить 1 из 3 точек → нажать Enter
2. Аннотация создаётся с 1 видимой (v=2) + 2 невидимыми (v=0)

### 4. YOLO Pose экспорт

1. **File → Export Dataset → YOLO Pose → Browse → Export**
2. Открыть `labels/train/<image>.txt`
3. Проверить: `0 cx cy w h x1 y1 2 x2 y2 0 x3 y3 0`
4. Открыть `data.yaml` → проверить: `kpt_shape: [3, 3]`

---

## Результаты тестов

| Файл | Результат |
|------|-----------|
| `test_phase7a.py` | **109/109 ✅** |
| `test_phase7.py` | 79/79 ✅ |
| `test_phase6.py` | 58/58 ✅ |
| `test_phase5.py` | 74/74 ✅ |
| `test_phase4.py` | 29/29 ✅ |
| `test_phase1.py` | 35/35 ✅ |

---

## Ограничения Phase 7A

- Нет drag-and-drop для перемещения уже размещённых ключевых точек
- Visibility = только 0 (невидима) или 2 (видима); v=1 (occluded) не поддерживается
- Bbox в YOLO Pose всегда авто-вычисляется из keypoints; ручной bbox не поддерживается
- Редактирование существующей POSE аннотации: через SelectTool (delete + пересоздать)

---

## Предложение для следующего этапа

Следующий этап по плану — **Phase 7 ML backend**: SAM/YOLO auto-label.
Перед реализацией необходимо отдельное обсуждение архитектуры (изолированный backend,
отдельное окружение Python, протокол общения с основным процессом).
