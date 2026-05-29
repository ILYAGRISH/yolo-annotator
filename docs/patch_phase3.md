# Патч к Фазе 3 — Привязка инструментов к типу класса

## Что изменилось

Два нарушения из обновлённой спецификации (`annotator-roadmap.md` → `## Dop`
и `architecture-notes.md`) не были реализованы в Фазе 3:

1. `annotation_type` должен быть иммутабельным после создания класса
2. `allowed_tools` должен показывать только инструменты, совместимые с типом

Кроме того, обнаружена практическая проблема: при выборе класса `object1 [bbox]`
пользователь мог рисовать полигоном или полилинией — поведение некорректное.

---

## Реализованные изменения

### `annotator/domain/label_class.py`

Добавлены две таблицы совместимости — единый источник правды для UI и тулбара:

```python
ANNOTATION_TYPE_TOOLS: dict[str, list[str]] = {
    "bbox":           ["bbox"],
    "polygon":        ["polygon"],
    "polyline":       ["polyline"],
    "obb":            ["obb"],
    "keypoints":      ["pose"],
    "classification": [],
}

ANNOTATION_TYPE_DEFAULT_TOOL: dict[str, str | None] = {
    "bbox":           "bbox",
    "polygon":        "polygon",
    "polyline":       "polyline",
    "obb":            None,   # инструмент не реализован
    "keypoints":      None,   # инструмент не реализован
    "classification": None,   # нет инструмента рисования
}
```

### `annotator/ui/dialogs/class_schema_editor.py`

**Иммутабельность `annotation_type`:**
- Кнопка `+ Add` теперь открывает мини-диалог `_NewClassDialog` с полями «Имя» + «Тип разметки»
- В правой форме редактора: для классов, созданных в текущей сессии — QComboBox; для существующих классов — bold QLabel (только чтение)
- При следующем открытии редактора все классы считаются существующими → тип везде plain text

**Фильтрация `allowed_tools`:**
- Чекбоксы инструментов отображаются только для совместимых с типом класса
- Для `classification` — надпись «No drawing tools — image-level label»
- `"select"` убран из списка инструментов (навигационный, не аннотационный)
- При смене типа (для нового класса) несовместимые выборы сбрасываются
- Локальная таблица `_COMPATIBLE_TOOLS` заменена импортом `ANNOTATION_TYPE_TOOLS` из доменного слоя

### `annotator/ui/main_window.py`

**Автопереключение инструмента при выборе класса:**
- Новый метод `_enforce_class_tool(lc)` вызывается при каждой смене класса в панели
- Если текущий инструмент несовместим с типом класса — автоматически активируется нужный
- Пример: выбрал `object1 [bbox]` → BBox активируется, Polygon/Polyline дизейблятся

**Блокировка несовместимых кнопок тулбара и меню:**
- Кнопки рисования (Polygon, Polyline, BBox) на тулбаре и в меню Tools дизейблятся, если не совместимы с текущим классом
- Select (`✦`) всегда доступен
- Для нереализованных типов (obb, keypoints) — все кнопки рисования дизейблятся

---

## Файлы патча

```
annotator/
  domain/
    label_class.py        (+ ANNOTATION_TYPE_TOOLS, ANNOTATION_TYPE_DEFAULT_TOOL)
  ui/
    dialogs/
      class_schema_editor.py  (иммутабельный тип, фильтрация чекбоксов, _NewClassDialog)
    main_window.py            (_enforce_class_tool, _menu_tool_acts, авто-переключение)
```

---

## Ручное тестирование

1. Открой проект → в Classes панели выбери `object1 [bbox]`
   → тулбар: активен BBox, Polygon и Polyline — серые (disabled)
2. Выбери `object2 [polygon]`
   → тулбар: активен Polygon, BBox и Polyline — серые
3. Выбери `object4 [classification]`
   → тулбар: все инструменты рисования серые, только Select доступен
4. Schema → Edit → выбери существующий класс
   → тип отображается как bold label (не dropdown)
5. Schema → Edit → `+ Add` → мини-диалог с именем и типом
   → после создания тип в правой форме — combo (ещё можно менять)
   → OK → снова открой Schema → тип уже label (стал existing)

---

## Регрессия

```
35 passed, 0 failed
```
