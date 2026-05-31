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

<!-- Следующие задачи будут добавлены ниже -->
