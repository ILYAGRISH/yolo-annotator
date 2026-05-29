# Отчёт о завершении Фазы 7C

## Итог

Фаза 7C реализует три блока практических улучшений:
1. **COCO export** — экспорт в стандартный формат COCO Instances JSON с поддержкой атрибутов
2. **CrackTool edit mode** — редактирование исходной полилинии существующей crack-аннотации
3. **Plugin loader** — автоматическая загрузка инструментов из `plugins/*.py`

---

## Блок 1 — COCO Export

**`annotator/exporters/coco.py`** — класс `CocoExporter`

### Формат вывода

```
<output_dir>/
  annotations/
    instances_train.json
    instances_val.json
    instances_test.json    (по одному файлу на сплит)
  images/
    train/                 (если copy_images=True)
    val/
```

### Поддерживаемые типы

| Тип аннотации | В COCO |
|---------------|--------|
| SEGMENT / POLYLINE | `segmentation`: плоский список пикселей `[x1,y1,x2,y2,...]` |
| BBOX | `bbox`: `[x, y, w, h]` в пикселях; `segmentation: []` |
| OBB | 4 угловых точки как `segmentation`-полигон |
| Атрибуты | поле `"attributes": {...}` в каждой аннотации (в отличие от YOLO) |

### Ключевые особенности

- ID классов 0-based (единообразно с YOLO)
- Пиксельные координаты: денормализованы из `(0-1)` через `img_rec.width/height`
- Если `width/height == 0` — читает размер изображения через Pillow
- `source_geometry` и `tool_params` crack-аннотаций **никогда не попадают** в вывод
- Атрибуты включаются в COCO (предупреждение "not exported" в диалоге не показывается)

### Интеграция

- `ExportDatasetDialog`: добавлен пункт "COCO Instances (JSON with attributes)"
- `ProjectController.export_dataset`: добавлена ветка `format_name == "coco"`
- Предупреждение об атрибутах в диалоге теперь условное: показывается только для YOLO-форматов

---

## Блок 2 — CrackTool: редактирование source polyline

### Сценарий использования

1. Выделить crack-аннотацию в Annotations Panel
2. Нажать кнопку **"Edit source"** (активна только если у аннотации есть `source_geometry`)
3. Инструмент переключается на CrackTool, загружает исходную полилинию
4. Пользователь добавляет/удаляет точки (RMB — удалить последнюю)
5. Enter или двойной клик → буфер пересчитывается, аннотация обновляется через undo-стек
6. Escape → отмена без изменений

### Изменения

**`annotator/tools/crack_tool.py`**:

| Добавлено | Описание |
|-----------|----------|
| `_edit_ann` | хранит редактируемую аннотацию (None = режим создания) |
| `is_editing` property | True когда активно редактирование |
| `start_edit(ann)` | загружает `source_geometry.points` + `tool_params`, рисует preview |
| `_commit()` | если `_edit_ann` — вызывает `update_annotation_data` (undo-able); иначе — `add_annotation` |
| `_cancel()` | очищает `_edit_ann` |

**`annotator/ui/panels/annotations_panel.py`**:
- Сигнал `edit_source_requested(str)` — ID аннотации
- Кнопка "Edit source": активна только если `"source_geometry" in ann.data`

**`annotator/ui/main_window.py`**:
- `_annotations_panel.edit_source_requested` → `_on_edit_crack_source(ann_id)`
- `_on_edit_crack_source`: находит аннотацию, переключает на CrackTool, вызывает `start_edit`

### Ограничения Phase 7C

- Нельзя перетаскивать существующие вершины — только добавлять (клик) и удалять последнюю (RMB)
- Редактирование начинается с уже существующих точек: можно расширять или обрезать полилинию
- Вставка точек в середину — в будущих фазах

---

## Блок 3 — Plugin Loader

**`annotator/plugins/loader.py`** — функция `load_plugins(plugins_dir)`

### Алгоритм

1. Сканирует `plugins_dir/*.py`
2. Пропускает файлы с `_` в начале имени
3. Импортирует каждый файл как изолированный модуль
4. Находит все подклассы `BaseTool`
5. Инстанциирует их
6. Ошибки импорта/инстанциации одного плагина не крашат загрузчик

### Интеграция в main_window

- `_load_plugins()` вызывается в `__init__` после `_setup_menu()`
- Найденные инструменты добавляются в `_tools` и в меню Tools (под разделителем)
- Plugin tools хранятся в `_plugin_tool_names` — не фильтруются по типу класса
- Без кнопки в тулбаре (плагин не знает заранее свою позицию в UI)

### Пример плагина

**`new_annotator/plugins/example_tool.py`** — `ExampleStampTool(BaseTool)` — скелет с комментариями о том, как реализовать drawing logic.

---

## Файлы Phase 7C

```
annotator/
  exporters/
    coco.py                      (новый — CocoExporter)
  tools/
    crack_tool.py                (+ start_edit, is_editing, edit mode в _commit/_cancel)
  plugins/
    loader.py                    (новый — load_plugins())
  ui/
    panels/
      annotations_panel.py       (+ кнопка Edit source, сигнал edit_source_requested)
    dialogs/
      export_dialog.py           (+ COCO в _FORMATS, условное предупреждение атрибутов)
    main_window.py               (+ _load_plugins, _on_edit_crack_source, _tools_menu ref,
                                    plugin tool filtering в _enforce_class_tool)
  controller/
    project_controller.py        (+ ветка "coco" в export_dataset)

new_annotator/
  plugins/
    __init__.py                  (новый — пустой)
    example_tool.py              (новый — пример плагина)
  test_phase7.py                 (новый — 79/79 checks)

docs/
  phase7c_completion_ru.md
```

---

## Команды запуска

```bat
cd new_annotator
run.bat                                        :: запуск приложения
.venv\Scripts\python test_phase7.py           :: тесты Phase 7C (79/79)
.venv\Scripts\python test_phase1.py           :: регрессия Phase 1-3 (35/35)
.venv\Scripts\python test_phase4.py           :: регрессия Phase 4 (29/29)
.venv\Scripts\python test_phase5.py           :: регрессия Phase 5 (74/74)
.venv\Scripts\python test_phase6.py           :: регрессия Phase 6 (58/58)
```

---

## Шаги ручного тестирования

### 1. COCO Export

1. Открыть проект с несколькими аннотациями (SEGMENT, BBOX, OBB)
2. **File → Export Dataset… → COCO Instances → Export**
3. Открыть `annotations/instances_train.json`
4. Проверить: categories, images, annotations
5. Проверить: для классов с атрибутами — предупреждение не показывается
6. Для YOLO-формата с атрибутами — предупреждение показывается

### 2. Edit source (crack)

1. Нарисовать crack-аннотацию (инструмент C)
2. В Annotations Panel выделить аннотацию
3. Кнопка "Edit source" стала активной
4. Нажать "Edit source" → переключился на CrackTool, preview показывает исходную полилинию
5. Кликнуть новые точки → preview обновляется
6. RMB → удалить последнюю точку
7. Enter → аннотация обновлена (новый полигон буфера)
8. Ctrl+Z → undo → аннотация вернулась к прежнему состоянию

### 3. Plugin loader

1. Запустить приложение
2. Меню Tools → Plugin: example_stamp (если `example_tool.py` в plugins/)
3. Нажать инструмент — переключился (ничего не рисует — это заглушка)
4. Добавить свой `.py` файл в `plugins/` → перезапустить → инструмент появился

---

## Результаты тестов

| Файл | Результат |
|------|-----------|
| `test_phase7.py` | **79/79 ✅** |
| `test_phase1.py` | 35/35 ✅ |
| `test_phase4.py` | 29/29 ✅ |
| `test_phase5.py` | 74/74 ✅ |
| `test_phase6.py` | 58/58 ✅ |

---

## Предложение для Фазы 7A (следующий этап)

| Компонент | Описание |
|-----------|----------|
| POSE инструмент | `PoseTool [K]` — клик по точкам скелета, `KeypointAnnotationItem` на канвасе |
| YOLO Pose экспорт | `class_id cx cy w h kx1 ky1 v1 kx2 ky2 v2 ...` |
| POSE canvas item | отображение ключевых точек и рёбер скелета |
| Skeleton schema | шаблон скелета в `class_schema.json` (keypoints: [{name, edges}]) |
