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

<!-- Следующие задачи будут добавлены ниже -->
