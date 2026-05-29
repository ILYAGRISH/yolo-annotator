# Отчёт о завершении Дополнения к Фазе 5

## Итог

Дополнение к Фазе 5 реализует два защитных предупреждения в подсистеме экспорта,
описанных в §8 документа `architecture-notes.md`.

---

## Что реализовано

### 1. Предупреждение об атрибутах при YOLO-экспорте

**`annotator/ui/dialogs/export_dialog.py`** — метод `_on_accept()`:

Перед подтверждением экспорта проверяется, есть ли в проекте классы с атрибутами.
Если да — показывается `QMessageBox.information`:

```
Class attributes will not be included in the YOLO export.
They are preserved in the project file (.annproj).
```

**Почему важно:** Атрибуты (`severity`, `material` и т.п.) хранятся во внутреннем
формате проекта и никогда не попадают в YOLO-файлы. Без предупреждения пользователь
может не знать, что аннотированные метаданные останутся за бортом обучающей выборки.
Атрибуты будут включены в будущий COCO-экспорт.

---

### 2. Предупреждение о несоответствии типа аннотации схеме класса

**`annotator/controller/project_controller.py`** — новый метод `get_type_mismatches()`:

```python
def get_type_mismatches(self) -> list[str]:
    """Return unique descriptions where ann.ann_type.value != class.annotation_type."""
```

Метод сканирует все сохранённые и in-memory аннотации. Для каждой проверяет:
`ann.ann_type.value == project.get_class(ann.class_id).annotation_type`.

Возвращает список уникальных расхождений вида:
```
"road_damage": schema=polygon, actual=bbox
```

**`annotator/ui/main_window.py`** — метод `_export_dataset()`:

После принятия диалога экспорта вызывается `get_type_mismatches()`.
Если список не пуст — показывается `QMessageBox.warning` с кнопками Yes / No:

```
Some annotations do not match their class schema type:

  • "road_damage": schema=polygon, actual=bbox

Mismatched annotations may be skipped during export. Continue?
```

По умолчанию выбрано **No** — пользователь должен явно подтвердить экспорт
с несоответствиями. При отмене экспорт не выполняется.

**Когда возникает несоответствие:** Если аннотации были созданы до смены
`annotation_type` у класса (смена типа — «опасная» операция по §2). В норме
этот диалог никогда не должен появляться.

---

## Что отложено (не входит в эту фазу)

| Пункт | Причина отложения |
|-------|-------------------|
| Shared images mode | Требует UI для одновременного экспорта нескольких форматов и другую структуру папок |
| COCO attributes | Нет COCO-экспортёра (Phase 7+) |

---

## Файлы дополнения

```
annotator/
  ui/
    dialogs/
      export_dialog.py      (+ attribute warning в _on_accept)
    main_window.py          (+ mismatch check в _export_dataset)
  controller/
    project_controller.py   (+ get_type_mismatches)

docs/
  phase5dop_completion_ru.md
```

---

## Команды запуска

```bat
cd new_annotator
.venv\Scripts\python test_phase1.py  :: регрессия Фаз 1–3 (35/35)
.venv\Scripts\python test_phase4.py  :: регрессия Фазы 4 (29/29)
.venv\Scripts\python test_phase5.py  :: регрессия Фазы 5 (74/74)
```

Новых автоматических тестов для этого дополнения нет — оба предупреждения
являются UI-диалогами и проверяются вручную.

---

## Шаги ручного тестирования

### 1. Предупреждение об атрибутах

1. Открыть проект с классом, у которого есть атрибуты (например, `severity: select`)
2. **File → Export Dataset…**
3. Выбрать любой формат + папку → нажать **Export**
4. Должен появиться диалог: "Attributes not exported. They are preserved in the project file."
5. Нажать OK → экспорт выполняется

### 2. Предупреждение о несоответствии типа

1. Создать класс с `annotation_type: polygon`
2. Вручную изменить тип класса на `bbox` через редактор схемы (после того как аннотации уже созданы)
3. **File → Export Dataset…** → Export
4. Должен появиться диалог с предупреждением о несоответствии
5. Нажать No → экспорт отменяется
6. Повторить → нажать Yes → экспорт выполняется (несоответствующие аннотации пропускаются)

---

## Критерии приёмки

| Критерий | Статус |
|----------|--------|
| Attribute warning появляется если у классов есть атрибуты | ✅ |
| Attribute warning НЕ появляется если атрибутов нет | ✅ |
| Mismatch warning появляется при расхождении schema vs actual | ✅ |
| По умолчанию в mismatch warning выбрано No | ✅ |
| Экспорт отменяется при выборе No в mismatch warning | ✅ |
| Регрессия Фаз 1–3: 35/35 | ✅ |
| Регрессия Фазы 4: 29/29 | ✅ |
| Регрессия Фазы 5: 74/74 | ✅ |

---

## Решение для Фазы 6 — Tool Properties Panel

Расположение: под тулбаром, над холстом — коллапсируемая полоса.
Скрыта когда нет активного параметризованного инструмента.
Видима только при активном Crack Tool (и будущих параметризованных инструментах).

Параметры рендерятся динамически из схемы `get_params_schema()` — без хардкода UI на каждый инструмент.
