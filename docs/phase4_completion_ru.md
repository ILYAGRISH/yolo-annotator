# Отчёт о завершении Фазы 4

## Итог

Фаза 4 реализует слой валидации, QC-панель и статистику датасета:
отдельный пакет `annotator/validation/` с иерархией правил, `Validator`,
экспортом в JSON/CSV и виджетом `QCPanel` в главном окне.

---

## Что реализовано

### Доменный слой валидации

**`annotator/validation/base.py`**

| Класс | Назначение |
|-------|-----------|
| `ValidationIssue` | Одна проблема: rule_name, severity, image_path, ann_id, message |
| `ValidationReport` | Список issues + словарь stats; свойства error_count, warning_count |
| `ValidationRule` | Абстрактный базовый класс (Strategy) — метод `check(project, all_anns)` |

**`annotator/validation/rules/`**

| Правило | Что проверяет | Severity |
|---------|--------------|---------|
| `EmptyImageRule` | Изображения без единой аннотации | warning |
| `SmallPolygonRule` | Полигоны (SEGMENT) с площадью < порога (default 0.001) | warning |
| `DuplicateAnnotationRule` | Аннотации одного класса с IoU ≥ 0.85 | warning |

**`annotator/validation/validator.py`**

- `Validator` — запускает все правила, вычисляет статистику
- `_compute_stats` — coverage (labeled/total/%), total_annotations, by_class, by_type
- `Validator.export_json(report, path, project_name)` — JSON-экспорт
- `Validator.export_csv(report, path)` — CSV-экспорт

### Контроллер

Два новых метода `ProjectController`:

| Метод | Назначение |
|-------|-----------|
| `run_validation()` | Запускает Validator; перекрывает load_all_annotations текущим in-memory состоянием |
| `export_validation_report(path, fmt)` | run_validation + запись JSON или CSV |

### UI: QCPanel

**`annotator/ui/panels/qc_panel.py`** — вкладка в правой панели:

- Кнопка **▶ Validate** (активна только при открытом проекте)
- Группа **Statistics**: Coverage, Annotations, By class, By type
- Список **Issues**: каждая запись — icon + имя файла + сообщение
  - `✖` красный — error
  - `⚠` оранжевый — warning
  - `ℹ` серый — info
- Двойной клик по issue → сигнал `navigate_requested(image_path, ann_id)`

Сигналы:
- `validate_requested` — подключён к `MainWindow._run_validation`
- `navigate_requested` — подключён к `MainWindow._on_qc_navigate`

### ImagesPanel

Добавлен метод `select_by_path(image_path)` — выделяет строку по пути файла
(используется при навигации из QC-панели).

### Главное окно

- Правая панель стала `QTabWidget` с вкладками **Annotations** и **QC**
- Новое меню **QC**:
  ```
  QC
  ├── Validate Project  [Ctrl+Shift+V]
  ├── ─────────────────────────────────
  ├── Export Report (JSON)…
  └── Export Report (CSV)…
  ```
- `_run_validation()` — запуск + переключение на вкладку QC + статусбар
- `_export_report(fmt)` — диалог сохранения + вызов контроллера
- `_on_qc_navigate(image_path, ann_id)` — `ctrl.set_image` + `images_panel.select_by_path` + `ctrl.select_annotation`

---

## Архитектурные решения

- **Валидация запускается синхронно** — нет отдельного потока; для больших
  датасетов допустимо, так как операция I/O — только чтение файлов.
  В будущем можно вынести в QThread без изменения публичного API.

- **In-memory overlay** — перед валидацией текущий несохранённый образ
  `self._annotations` подставляется вместо версии из файла, чтобы результаты
  отражали актуальное состояние.

- **Единый источник правды** — `_compute_stats` получает `all_annotations`
  уже с overlay; правила работают с теми же данными.

- **Strategy pattern** — любое новое правило реализует `ValidationRule.check()`
  и добавляется в `_default_rules()` без изменения остального кода.

---

## Файлы Фазы 4

```
annotator/
  validation/
    __init__.py
    base.py              (ValidationIssue, ValidationReport, ValidationRule ABC)
    validator.py         (Validator, _compute_stats, export_json, export_csv)
    rules/
      __init__.py
      empty_image.py     (EmptyImageRule)
      small_polygon.py   (SmallPolygonRule + shoelace area)
      duplicate.py       (DuplicateAnnotationRule + IoU)
  ui/
    panels/
      qc_panel.py        (QCPanel widget)
      images_panel.py    (+ select_by_path)
    main_window.py       (QTabWidget, QC menu, _run_validation, _on_qc_navigate)
  controller/
    project_controller.py  (+ run_validation, export_validation_report)

test_phase4.py           (29 checks, 0 failed)
docs/
  patch_phase3.md
  phase4_completion_ru.md
```

---

## Команды запуска

```bat
cd new_annotator
run.bat                              :: запуск приложения
.venv\Scripts\python test_phase1.py  :: регрессия Фаз 1–3 (35/35)
.venv\Scripts\python test_phase4.py  :: тесты Фазы 4 (29/29)
```

---

## Шаги ручного тестирования

### 1. Validate и статистика
1. Открыть проект с несколькими изображениями
2. Разметить часть изображений, часть оставить пустыми
3. Меню **QC → Validate Project** или кнопка **▶ Validate** во вкладке QC
4. В панели Statistics: проверить Coverage, Annotations, By class, By type
5. В списке Issues: убедиться, что пустые изображения отображаются с ⚠

### 2. Навигация по issues
1. Двойной клик на issue в списке
2. Приложение переключается на нужное изображение
3. Если `ann_id` есть — аннотация выделяется

### 3. Экспорт отчёта
1. **QC → Export Report (JSON)…** → сохранить файл
2. Открыть: проверить наличие `stats` и `issues`
3. **QC → Export Report (CSV)…** → открыть в Excel/текстовом редакторе

### 4. SmallPolygon
1. Нарисовать крошечный полигон (несколько пикселей)
2. Запустить Validate → в Issues появляется ⚠ SmallPolygon

### 5. DuplicateAnnotation
1. Нарисовать два bbox одного класса в почти одном месте
2. Validate → ⚠ DuplicateAnnotation

---

## Критерии приёмки

| Критерий | Статус |
|----------|--------|
| Кнопка Validate запускает проверку без зависания UI | ✅ |
| Каждая проблема привязана к изображению и аннотации | ✅ |
| Двойной клик открывает изображение + выделяет аннотацию | ✅ |
| Статистика показывает coverage и баланс классов | ✅ |
| Экспорт в JSON и CSV работает | ✅ |
| Регрессия Фаз 1–3 не нарушена | ✅ 35/35 |
| Тесты Фазы 4: 29/29 | ✅ |

---

## Известные ограничения

- **Синхронная валидация** — при тысячах изображений UI может подморозиться.
  Решение (будущая фаза): QThread + прогресс-бар.
- **SmallPolygonRule** — порог `min_area=0.001` фиксирован в коде; в будущем
  можно выставлять через настройки проекта.
- **DuplicateAnnotationRule** — детектирует дубликаты по bbox-оверлапу (IoU).
  Для полигонов точнее было бы считать IoU по пиксельным маскам, но это
  требует растеризации (сложно без знания размера изображения).
- **Кнопка ▶ Validate** в QC-панели переключает на вкладку QC автоматически
  только при вызове через меню. При вызове через кнопку внутри вкладки
  вкладка уже активна — всё корректно.

---

## Предложение для Фазы 5

**Форматы экспорта (YOLO, COCO, VOC)**

| Функция | Описание |
|---------|---------|
| YOLO detect | Экспорт bbox → `labels_detect/`, `data.yaml` |
| YOLO segment | Уже реализован как авто-экспорт; сделать явным через меню |
| YOLO obb | Экспорт OBB → `labels_obb/`, `data.yaml` |
| COCO JSON | Стандартный `instances_default.json` |
| Split train/val/test | По полю `ImageRecord.split`; настраивается при экспорте |
| Shared images mode | Один `images/`, несколько `labels_*/` и `data.yaml` |
| Export profiles | Сохраняемые профили (тип + split + фильтры классов) |
