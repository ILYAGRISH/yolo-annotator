# Phase 7fix — отчёт о доработках

> Фаза 7fix — исправления и дополнения по результатам ручного тестирования после Phase 7A.
> Документ дополняется по мере выполнения задач.

---

## Задача 1 — Реализация типа CLASSIFY (image-level classification)

### Проблема
- При выборе класса `classification` все кнопки инструментов дизейблились, но активный инструмент сцены не менялся — можно было рисовать bbox на classification-классе.
- Инструмент разметки классификации отсутствовал; тип CLASSIFY существовал только в домене.

### Решение — Вариант A: image-level tag через кнопку

**`annotator/ui/panels/annotations_panel.py`**
- Добавлен сигнал `classify_image_requested = pyqtSignal(int)` (class_id)
- Добавлена кнопка `"+ Classify as <name>"` (скрыта по умолчанию, появляется только для classification-классов)
- Добавлен метод `set_active_class(cls)` — показывает/скрывает кнопку при смене класса
- CLASSIFY-аннотации отображаются как `[IMAGE LABEL]` вместо `[classify] (0 pts)`

**`annotator/ui/main_window.py`**
- `_enforce_class_tool`: при `annotation_type == "classification"` принудительно переключается на Select tool (баг-фикс)
- `_on_class_selected`: добавлен вызов `self._annotations_panel.set_active_class(lc)`
- Добавлен слот `_on_classify_image(class_id)`:
  - Проверяет дубль: если CLASSIFY-аннотация для этого класса уже есть — показывает предупреждение
  - Создаёт `Annotation.new(class_id, AnnotationType.CLASSIFY, {})`

**`annotator/exporters/yolo_classify.py`** (новый)
- `YoloClassifyExporter(BaseExporter)`
- Структура вывода: `output_dir/{split}/{class_name}/image.jpg`
- Копирует изображение в папку класса для каждой CLASSIFY-аннотации
- Многолейбловая разметка поддерживается (разные классы на одном изображении)

**`annotator/ui/dialogs/export_dialog.py`**
- Добавлен формат: `"YOLO Classify  (image-level classification)"` / `"yolo_classify"`

**`annotator/controller/project_controller.py`**
- Добавлена ветка `elif format_name == "yolo_classify"`

### Формат экспорта YOLO Classify
```
output/
  train/
    cat/
      img1.jpg
      img3.jpg
    dog/
      img2.jpg
  val/
    cat/
      img4.jpg
```
> Нет `data.yaml` и `labels/` — только папочная структура по классам.

### Workflow разметки
1. Создать класс типа `classification` в Schema Editor
2. Выбрать его в Classes Panel → все drawing-инструменты блокируются, активируется Select
3. В Annotations Panel появляется кнопка `+ Classify as "имя_класса"`
4. Нажать кнопку → CLASSIFY-аннотация создаётся (Undo/Redo работает)
5. Повторный клик на кнопку → предупреждение "Already labeled"
6. Экспорт: File → Export Dataset → YOLO Classify

### Файлы задачи 1
```
annotator/
  ui/
    panels/annotations_panel.py   (+ classify button, signal, set_active_class)
    main_window.py                 (+ _on_classify_image, _enforce fix, set_active_class call)
    dialogs/export_dialog.py       (+ YOLO Classify в _FORMATS)
  exporters/
    yolo_classify.py               (новый)
  controller/
    project_controller.py          (+ ветка yolo_classify)
```

---

---

## Задача 2 — Close Project (закрытие проекта)

### Проблема
Отсутствовал пункт "Close Project" в меню File.

### Решение

**`annotator/controller/project_controller.py`**
- `is_dirty: bool` — property, возвращает `True` если есть несохранённые аннотации
- `close_project()` — очищает состояние, сбрасывает `_project = None`, эмитит `project_changed(None)`

**`annotator/ui/main_window.py`**
- File → "Close Project" (после Save Project, до разделителя)
- `_close_project()`: если `is_dirty` → диалог Save / Discard / Cancel; затем `ctrl.close_project()`
- `_on_project_changed(None)`: очищает канвас, сбрасывает заголовок окна, показывает стартовый статус

### Поведение
| Состояние | Действие |
|-----------|----------|
| Проект сохранён | Закрывается без вопросов |
| Есть несохранённые аннотации | Диалог: Save / Discard / Cancel |
| Save | `save_project()` → `close_project()` |
| Discard | `close_project()` без сохранения |
| Cancel | Проект остаётся открытым |

---

## Задача 3 — Project Settings (настройки проекта)

### Проблема
Диалог создания проекта содержал только имя и папку. Остальные поля `ProjectSettings` были недоступны для просмотра и редактирования.

### Решение
Новый диалог **File → Project Settings…** для открытого проекта.

**`annotator/ui/dialogs/project_settings_dialog.py`** (новый)
- **Name** — редактируемое имя проекта
- **Settings (группа)**:
  - Default export format — QComboBox (все 6 форматов)
  - Autosave interval — QSpinBox (10–3600 сек)
- **Info (read-only группа)**:
  - Created / Modified — даты из project.json
  - ID — UUID проекта

**`annotator/controller/project_controller.py`**
- `update_project_settings(name, settings)` — обновляет имя и `ProjectSettings`, сохраняет проект, эмитит `project_changed`

**`annotator/ui/main_window.py`**
- File → "Project Settings…" (после Close Project)
- `_open_project_settings()`: открывает диалог, применяет изменения, немедленно обновляет интервал autosave-таймера

### File меню (итоговый порядок)
```
New Project…      Ctrl+N
Open Project…     Ctrl+O
Save Project      Ctrl+S
Close Project
Project Settings…
──────────────────────
Add Images from Folder…
──────────────────────
Export Dataset…   Ctrl+E
──────────────────────
Quit              Ctrl+Q
```

---

## Задача 4 — Удаление класса (Delete class в Schema Editor)

### Проблема
`ClassDeleteDialog` был реализован в Phase 3, но нигде не вызывался. Удалить класс из проекта было невозможно.

### Решение

**`annotator/ui/dialogs/class_schema_editor.py`**
- Конструктор принимает опциональный `count_fn(class_id) -> int` — функцию подсчёта аннотаций
- Новая красная кнопка **`− Delete`** в левой панели (рядом с `+ Add`, `↑`, `↓`)
- `_pending_deletions: list[tuple[int, int|None]]` — список удалений, применяемых после OK
- `property pending_deletions` — доступ из main_window
- Метод `_delete_class()`:
  - Новый класс (создан в этой сессии, не сохранён) — удаляется молча, без диалога
  - Сохранённый класс — открывается `ClassDeleteDialog` с количеством аннотаций и выбором действия
  - Последний класс — блокируется с предупреждением (схема не может быть пустой)

**`annotator/ui/main_window.py`**
- `_open_schema_editor` передаёт `count_fn=self._ctrl.count_annotations_for_class`
- После OK: `self._ctrl.delete_class(class_id, reassign_to)` для каждого элемента `pending_deletions`
- `delete_class` сам вызывает `save_project()` и `project_changed.emit()`, поэтому дублирования нет

### Workflow удаления класса
1. **Schema → Edit Class Schema**
2. Выбрать класс в левом списке
3. Нажать **`− Delete`**
4. Диалог: показывает количество аннотаций → выбор **Reassign to…** / **Delete all annotations** / **Cancel**
5. Нажать **OK** в Schema Editor — удаление применяется к файлам аннотаций

### Защиты
| Ситуация | Поведение |
|----------|-----------|
| Последний класс | Предупреждение, удаление заблокировано |
| Класс только что создан (не сохранён) | Молчаливое удаление из списка |
| Cancel в диалоге | Класс остаётся, Cancel отменяет только это действие |
| Cancel в Schema Editor | Все изменения включая pending_deletions откатываются |

---

## Задача 5 — Редактирование атрибута класса

### Проблема
Атрибуты класса можно было добавить и удалить, но не отредактировать. При опечатке в имени или необходимости изменить тип/опции приходилось удалять атрибут и создавать заново.

### Решение

**`annotator/ui/dialogs/class_schema_editor.py`**
- `_AttributeDialog.__init__` — добавлен параметр `attr: ClassAttribute | None = None`:
  - если передан — заголовок меняется на `"Edit attribute"`, поля предзаполняются текущими значениями
  - предзаполнение: name, type (setCurrentIndex), options (для select), default value
- `ClassSchemaEditorDialog._build_ui` — подключён сигнал `cellDoubleClicked` таблицы атрибутов → `_edit_attribute`
- Новый метод `_edit_attribute(row, col)`:
  - открывает `_AttributeDialog(attr=attr)` с предзаполнением
  - после OK обновляет поля атрибута в модели (`name`, `attr_type`, `options`, `default_value`)
  - UUID атрибута не меняется — существующие аннотационные данные не затрагиваются
  - обновляет строку в таблице без перестройки всей таблицы

### Баг-фикс (в том же коммите)
`__init__` вызовы `_build_ui()`, `_refresh_list()`, `setCurrentRow(0)` оказались внутри тела property `pending_deletions` (мёртвый код после `return`) — окно открывалось пустым. Перенесены в конец `__init__`.

### Workflow редактирования атрибута
1. **Schema → Edit Class Schema**
2. Выбрать класс в левом списке
3. Дважды кликнуть по строке атрибута в таблице Attributes
4. Изменить name / type / options / default → OK
5. Строка обновляется немедленно; изменения применяются после OK в Schema Editor

---

## Задача 6 — Cosmetic rendering: хэндлы и превью

### Проблема
- Хэндлы выделенных аннотаций (polygon, bbox, obb, pose) задавались в координатах сцены (`HANDLE_R = 5.0`). При типичном зуме ≈0.3 это 1–2 экр.пикс. — почти невидимо.
- Точки и линии при рисовании (preview в инструментах) — та же проблема.
- `display_style` (line_width, opacity) из схемы классов хранился, но нигде не применялся к отрисовке.
- CrackTool: заливка превью слишком прозрачная (alpha=55).
- Polygon: snap-индикатор замыкания контура практически невидим.

### Решение

**`annotator/ui/canvas/items/base_item.py`**
- Добавлены поля `line_width: float = 2.0` и `fill_opacity: float = 0.3`

**`annotator/ui/canvas/items/polygon_item.py`, `bbox_item.py`, `obb_item.py`, `pose_item.py`**
- `HANDLE_R` → `HANDLE_SCREEN_R = 5.0` (экранные пиксели)
- В `paint()`: `lod = option.levelOfDetailFromTransform(...)`, `handle_r = HANDLE_SCREEN_R / lod` — хэндлы постоянного экранного размера
- `_lod` кэшируется для `handle_at()` — зона клика тоже масштабируется
- `paint()` использует `self.line_width` и `self.fill_opacity` вместо hardcoded значений
- `_BOUNDING_MARGIN = 30.0` — запас bounding rect для cosmetic хэндлов

**`annotator/ui/canvas/scene.py` → `_make_item()`**
- После создания item: `item.line_width = cls.display_style.line_width`, `item.fill_opacity = cls.display_style.opacity`
- Рефакторинг: `return item` вместо множества `return X` → display_style применяется единообразно

**`annotator/tools/base.py`**
- `_view_lod()` — текущий zoom-фактор из `scene.views()[0].transform().m11()`
- `_cosmetic_pen(color, width, style)` — pen с `setCosmetic(True)`: ширина в экр.пикс.

**`annotator/tools/polygon_tool.py`**
- `CLOSE_THRESHOLD_SCREEN = 15` (вместо 12 scene units) — зона замыкания динамически масштабируется
- `_near_first()` использует `_view_lod()` для корректного threshold
- `_refresh_preview()`: cosmetic pens, `dot_r = 5.0/lod`, snap-кольцо `snap_r = 11.0/lod`

**`annotator/tools/crack_tool.py`**
- `_refresh_preview()`: cosmetic pens, `dot_r = 5.0/lod`, fill alpha 55 → 90

### Карта параметров (для быстрого поиска)

| Параметр | Файл | Место |
|----------|------|-------|
| Размер хэндла (экр.пикс.) | `items/*_item.py` | `HANDLE_SCREEN_R = 5.0` |
| Дефолт line_width | `items/base_item.py` | `self.line_width = 2.0` |
| Дефолт fill_opacity | `items/base_item.py` | `self.fill_opacity = 0.3` |
| Точки превью (экр.пикс.) | `tools/polygon_tool.py`, `crack_tool.py` | `dot_r = 5.0 / lod` |
| Кольцо замыкания (экр.пикс.) | `tools/polygon_tool.py` | `snap_r = 11.0 / lod` |
| Заливка превью CrackTool | `tools/crack_tool.py` | `QColor(255, 170, 0, 90)` |
| Зона замыкания (экр.пикс.) | `tools/polygon_tool.py` | `CLOSE_THRESHOLD_SCREEN = 15` |

---

## Задача 7 — CrackTool: Edit source — полная реализация и фиксы

### Проблема (многоуровневая)

1. **Кнопка Edit source всегда неактивна** — `set_selected()` в панели Annotations использовал `blockSignals(True)`, из-за чего `_on_row` (обновляющий состояние кнопки) никогда не срабатывал при выборе разметки с канваса.
2. **Перетаскивание вершин отсутствовало** — при клике на существующую вершину добавлялась новая точка поверх неё; `_drag_idx` не был реализован.
3. **Tool Props не синхронизировался** — после `start_edit()` панель Tool Props показывала дефолтные параметры буфера, а не те, с которыми была создана аннотация.
4. **Резиновая нить в режиме Edit source** — при движении мыши после активации Edit source от последней точки к курсору тянулась линия, создавая ощущение, что добавляется новая точка.
5. **Двойной клик на вершине** — первый клик дабл-клика попадал на вершину → начинался drag; `on_double_click` затем удалял _последнюю_ точку (неправильную) перед подтверждением.
6. **После подтверждения: нет обратного переключения** — после Enter/двойного клика инструмент оставался CrackTool, аннотация не выделялась в панели Annotations, кнопка Edit source была неактивна.

### Решение

**`annotator/ui/panels/annotations_panel.py`**
- `set_selected()`: вместо `blockSignals(True)` вокруг `setCurrentRow` — ищет аннотацию по id, напрямую устанавливает состояние кнопки `_btn_edit_src` по результату поиска. Сигналы больше не блокируются.

**`annotator/tools/crack_tool.py`**
- Добавлен `self._drag_idx: int = -1` — индекс перетаскиваемой вершины (-1 = не перетаскивается)
- `_vertex_at(pos)`: возвращает индекс ближайшей вершины в радиусе 8 экр.пикс. (с учётом lod)
- `on_press`: сначала проверяет `_vertex_at` → если попали на вершину: drag; иначе: добавить точку. ПКМ во время drag отменяет перетаскивание (вместо удаления точки)
- `on_move`: если `_drag_idx >= 0` → двигает вершину + `_refresh_preview(None)`; иначе в edit-режиме — `cursor=None` (без резиновой нити)
- `on_release`: сбрасывает `_drag_idx`, обновляет превью без резиновой нити в edit-режиме
- `on_double_click`: `was_dragging = _drag_idx >= 0`; если drag — не удаляет точку, только подтверждает
- `_commit()` (edit-ветка): добавлен вызов `self._ctrl.select_annotation(edit_id)` после `update_annotation_data`
- `_cancel()`: сбрасывает `_drag_idx`

**`annotator/ui/main_window.py`**
- `_on_edit_crack_source()`: после `crack.start_edit(ann)` добавлен вызов `self._tool_props.load_tool(crack)` — панель показывает параметры из аннотации
- `_on_annotation_selected()`: после обновления сцены и панели — проверяет, активен ли `crack_tool` и НЕ находится ли он в режиме редактирования (`not crack.is_editing`); если да — переключается на Select tool. Это обеспечивает автоматический возврат после подтверждения.

### Итоговый workflow Edit source
1. Выделить crack-разметку (Select)
2. Нажать **Edit source** → кнопка активна, загружается исходная полилиния, узлы видны, резиновой нити нет
3. Tool Props показывает параметры буфера из аннотации
4. **Перетащить** вершину — зажать ЛКМ на узле → тянуть. Буферный полигон обновляется live
5. Изменить параметры буфера в Tool Props — превью пересчитывается немедленно
6. **Enter** или **двойной клик** → подтверждение: полигон пересчитывается, инструмент переключается на Select, аннотация выделяется в панели, Edit source активна

### Файлы задачи 7
```
annotator/
  tools/
    crack_tool.py      (drag, rubber-band fix, double-click fix, select_annotation)
  ui/
    panels/annotations_panel.py  (set_selected без blockSignals, кнопка Edit source)
    main_window.py               (_on_annotation_selected: auto-switch; load_tool после start_edit)
```

## Задача 8 — PoseTool: рёбра скелета и cosmetic rendering

### Проблема (три пункта)

1. **Рёбра скелета не сохранялись** — поле `Edges (i-j pairs)` принимало ввод вида `"0-1, 0-2"` (с кавычками), которые пользователь добавлял интуитивно, опираясь на подсказку-плейсхолдер. `int("'0")` бросал `ValueError` → пары парсились в `[]` → `edges: []` в JSON.
2. **Размер точек при рисовании зависел от масштаба** — радиус задавался в координатах сцены (`r = 5`), а не экранных пикселях.
3. **Рёбра скелета не отображались при рисовании и в готовой разметке** — все перья были scene-unit width.

### Решение

**`annotator/ui/dialogs/class_schema_editor.py`**
- `_parse_edges` переписан с `re.finditer(r'(\d+)-(\d+)', text)` — regex извлекает пары `N-N` из любого текста, игнорируя кавычки, пробелы и прочие символы
- Добавлен `import re`
- Плейсхолдер `Edges` изменён: `e.g. "0-1, 1-2, 1-5"` → `e.g. 0-1, 1-2, 1-5` (без кавычек)
- Удалены отладочные `print([DEBUG ...])` из `_sync_skeleton` и `_accept`

**`annotator/tools/pose_tool.py`**
- `_refresh_preview()`: `r = 5.0 / max(lod, 0.05)` — радиус точки в экранных пикселях
- `edge_pen = self._cosmetic_pen("#00FF88", 1.5)` — рёбра при рисовании cosmetic
- `dot_pen = self._cosmetic_pen("#FFFFFF", 1.0)` — граница точки cosmetic

**`annotator/ui/canvas/items/pose_item.py`**
- `edge_pen.setCosmetic(True)` — рёбра готовой разметки постоянной ширины
- `border_pen.setCosmetic(True)` — граница точек-ключевых постоянной ширины

**`test_phase7a.py`, `test_phase7.py`**
- Добавлен `_MockView` с `transform().m11() = 1.0`
- `_MockScene.views()` возвращает `[_MockView()]` — без этого `_view_lod()` падал в headless-тестах
- `_MockCtrl.select_annotation()` — заглушка для тестов CrackTool в edit-режиме

### Файлы задачи 8
```
annotator/
  ui/
    dialogs/class_schema_editor.py  (_parse_edges regex, плейсхолдер без кавычек)
  tools/
    pose_tool.py                    (cosmetic pens, LOD-based dot radius)
  ui/canvas/items/
    pose_item.py                    (cosmetic edge_pen и border_pen)
test_phase7a.py                     (_MockView, _MockScene.views)
test_phase7.py                      (_MockView, _MockScene.views, _MockCtrl.select_annotation)
```

---

## Задача 9 — Images panel: галочка ✓ для размеченных файлов

### Проблема
- Файлы с аннотациями отображались зелёным цветом (`#55CC55`) через `mark_annotated()`
- Это перекрывало цвет `val` (синий) и `test` (оранжевый) — нельзя было одновременно видеть и наличие разметки, и принадлежность к сплиту

### Решение

**`annotator/ui/panels/images_panel.py`**
- Добавлен `self._annotated: set[str]` — набор путей изображений с аннотациями
- `_scan_annotated(project)` — при загрузке проекта сканирует `annotations/*.json`, добавляет в set если размер файла > 5 байт (т.е. не пустой `[]`)
- `_make_item()`: вместо зелёного цвета добавляет суффикс ` ✓` если путь в `_annotated`; цвет split сохраняется
- `mark_annotated()` → `set_annotated(path, has: bool)` — обновляет set и вызывает `_refresh_item()`. Работает в обе стороны: при добавлении ✓ появляется, при удалении последней аннотации — исчезает

**`annotator/ui/main_window.py`**
- `_on_annotations_changed`: `mark_annotated(path)` → `set_annotated(path, bool(annotations))` — теперь вызывается всегда (не только при наличии аннотаций), передаёт `False` когда аннотации удалены

### Итоговый вид списка Images
```
CA1000148_1_i.jpg ✓          ← train (дефолт), есть разметка
CA1000235_1_d.jpg [val]      ← val, нет разметки  (синий)
CA1000504_1_d.jpg [test] ✓   ← test, есть разметка (оранжевый)
CA1000713_1_d.jpg [val] ✓    ← val, есть разметка  (синий)
```

### Файлы задачи 9
```
annotator/
  ui/
    panels/images_panel.py   (_annotated set, _scan_annotated, set_annotated, _make_item с ✓)
    main_window.py           (set_annotated вместо mark_annotated, передаёт bool)
```

## Задача 10 — Point Tool (одиночная точка)

### Что реализовано

Новый тип аннотации `POINT` и одноимённый инструмент для разметки одиночных точек (центроиды, ориентиры, подсчёт объектов). Отличие от Pose: нет скелета, нет множества точек, нет имён — один клик = одна аннотация.

### Детали реализации

**`annotator/domain/annotation.py`**
- Добавлен `AnnotationType.POINT = "point"`
- Схема данных: `{"x": float, "y": float}` (нормализованные [0, 1])

**`annotator/domain/label_class.py`**
- `"point"` добавлен в `ANNOTATION_TYPES`, `ANNOTATION_TYPE_TOOLS`, `ANNOTATION_TYPE_DEFAULT_TOOL`
- Совместимый инструмент: `["point"]`; авто-активация: `"point"`

**`annotator/tools/point_tool.py`** (новый)
- Горячая клавиша: `.` (точка)
- ЛКМ → аннотация создаётся немедленно (не нужен Enter)
- Превью: ghost-кружок следует за курсором; Esc — скрыть превью
- Размер ghost — LOD-based (5 экр.пикс.)

**`annotator/ui/canvas/items/point_item.py`** (новый)
- Cosmetic dot с белой границей; при выделении — дополнительное кольцо
- `PT_SCREEN_R = 6.0` (экр.пикс.), `PT_HIT = 10.0` (scene units) — зона клика

**`annotator/ui/canvas/scene.py`**
- Добавлена ветка `AnnotationType.POINT → PointAnnotationItem` в `_make_item()`

**`annotator/exporters/yolo_point.py`** (новый)
- Формат: `class_id cx cy 0.01 0.01 x y 2` (YOLO 1-keypoint pose + синтетический bbox 1%)
- `data.yaml` дополняется `kpt_shape: [1, 3]`

**`annotator/ui/main_window.py`**, **`export_dialog.py`**, **`project_controller.py`**
- Кнопка `• Point [.]` в тулбаре и меню Tools
- Формат `YOLO Point (single point → 1-kpt pose)` в диалоге экспорта

### Файлы задачи 10
```
annotator/
  domain/
    annotation.py              (+ POINT enum)
    label_class.py             (+ "point" в словари)
  tools/
    point_tool.py              (новый)
  ui/canvas/items/
    point_item.py              (новый)
  ui/canvas/
    scene.py                   (+ POINT ветка)
  ui/
    main_window.py             (+ импорт, toolbar, menu, _build_tools)
    dialogs/export_dialog.py   (+ YOLO Point)
  exporters/
    yolo_point.py              (новый)
  controller/
    project_controller.py      (+ yolo_point ветка)
```

---

## Задача 11 — Brush/Mask tool (бинарные маски сегментации)

### Что реализовано

Новый инструмент рисования бинарных масок кистью. Результат сохраняется как PNG и экспортируется в YOLO seg через контурный полигон.

### Детали реализации

**`annotator/domain/annotation.py`**
- Добавлен `AnnotationType.MASK = "mask"`

**`annotator/storage/mask_storage.py`** (новый)
- `MaskStorage` — save/load PNG (grayscale, uint8)
- `mask_to_polygon(bitmap, w, h)` — контур через `cv2.findContours` → нормализованные координаты
- `mask_to_bbox(bitmap, w, h)` — bounding box из ненулевых пикселей

**`annotator/tools/brush_tool.py`** (новый)
- Горячая клавиша: `M`
- Рисование/стирание: `cv2.circle` на numpy uint8 bitmap
- Overlay: numpy → RGBA QImage → QPixmap (fix: `raw = rgba.tobytes()` + `.copy()` против use-after-free)
- Enter / double-click = commit; Esc = discard (с восстановлением оригинала)
- Re-edit (Select нужную маску → M): загружает PNG в canvas, оригинал восстанавливается при Esc
- Авто-загрузка: первый Erase-мазок на пустом canvas → загружает последнюю маску класса

**`annotator/ui/canvas/items/mask_item.py`** (новый)
- `MaskAnnotationItem` — отрисовка заполненным полигоном контура
- `handle_at() → -1` (нет вершин для перетаскивания)

**`annotator/ui/panels/tool_props_panel.py`**
- Добавлена поддержка типа `"int"` (QSpinBox) — используется для `brush_size`

**`annotator/ui/canvas/scene.py`**, **`main_window.py`**, **`exporters/yolo_seg.py`**, **`storage/project_store.py`**
- Регистрация BrushTool, MaskAnnotationItem, экспорт YOLO seg через `ann.data["polygon"]`

### Workflow
1. Выбрать класс → нажать `M`
2. Рисовать кистью (ЛКМ + drag); Erase mode — стирает
3. Enter или двойной клик → commit (маска сохраняется как PNG, появляется в Annotations)
4. Esc → discard (если маска была загружена для ре-едита — возвращается на место)
5. Re-edit: Select нужную маску → M → маска загружается в canvas → Enter сохраняет новую версию

### Файлы задачи 11
```
annotator/
  domain/
    annotation.py              (+ MASK enum)
    label_class.py             (+ "mask" в словари)
  storage/
    mask_storage.py            (новый)
  tools/
    brush_tool.py              (новый)
  ui/canvas/items/
    mask_item.py               (новый)
  ui/canvas/
    scene.py                   (+ MASK ветка)
  ui/
    main_window.py             (+ BrushTool регистрация)
    panels/tool_props_panel.py (+ int spinbox)
  exporters/
    yolo_seg.py                (+ MASK экспорт)
  controller/
    project_controller.py      (minor)
```

---

## Баг-фиксы (после тестирования задачи 11)

### Фикс 1 — Потеря маски при Esc после загрузки для ре-едита

**Проблема:** `_load_mask_into_canvas()` удалял аннотацию из контроллера сразу при загрузке (чтобы избежать двойного рендеринга). При нажатии Esc canvas очищался, но оригинальная аннотация не восстанавливалась — данные терялись безвозвратно.

**Сценарий:** Select → клик на маску → M (загрузка в canvas) → Esc → маска исчезает.

**Решение (`annotator/tools/brush_tool.py`):**
- `self._editing_ann` сохраняет оригинальную аннотацию при загрузке
- `_reset_canvas()` (Esc) — восстанавливает `_editing_ann` через `ctrl.add_annotation()`
- `deactivate()` — то же, если пользователь переключился на другой инструмент
- `_commit()` — очищает `_editing_ann` перед `_reset_canvas()` (новая версия уже добавлена)

### Фикс 2 — Хоткей M не работал

**Проблема:** Каждый инструмент регистрировал шорткат дважды — в пункте меню Tools и в кнопке тулбара. Qt трактовал это как "ambiguous shortcut" и не активировал ни один из них.

**Решение (`annotator/ui/main_window.py`):**
- Шорткаты убраны из пунктов меню Tools (текст `[M]` в названии остался для информации)
- Шорткаты остались только на кнопках тулбара (единственный canonical источник)
- Исправление применено ко всем инструментам (V, P, L, B, O, C, K, ., M)
