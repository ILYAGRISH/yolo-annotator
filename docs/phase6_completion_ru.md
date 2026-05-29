# Отчёт о завершении Фазы 6

## Итог

Фаза 6 реализует Crack Tool — специализированный инструмент разметки трещин на асфальте.
Инструмент рисует полилинию, буферизует её через shapely и сохраняет результат
как SEGMENT-аннотацию с встроенной исходной геометрией (`source_geometry`) и
параметрами буфера (`tool_params`).

Также реализована Tool Properties Panel — динамическая панель параметров,
появляющаяся под тулбаром при активации параметризованного инструмента.

---

## Что реализовано

### Блок 1 — CrackTool

**`annotator/tools/crack_tool.py`**

| Поведение | Описание |
|-----------|----------|
| Рисование | Клик = добавить точку полилинии (горячая клавиша **C**) |
| Отмена точки | ПКМ — удаляет последнюю точку |
| Финализация | Двойной клик или Enter |
| Отмена | Escape |
| Preview | Оранжевая пунктирная полилиния + полупрозрачный буферный полигон в реальном времени |
| Обновление | При изменении параметров в Tool Properties Panel preview перестраивается немедленно |

**Результирующая аннотация:**

```json
{
  "type": "segment",
  "data": {
    "points": [[x,y], ...],
    "source_geometry": {
      "type": "polyline",
      "points": [[x,y], ...]
    },
    "tool_params": {
      "buffer_width": 0.008,
      "cap_style": "round",
      "join_style": "round",
      "simplify": 0.001
    }
  }
}
```

**Функция `_buffer_polyline(norm_pts, params, image_size)`:**
- Принимает нормализованные точки (0–1), параметры буфера, размер изображения
- Использует `shapely.LineString.buffer()` в пиксельных координатах
- Возвращает нормализованные координаты внешнего контура буферного полигона
- При `simplify > 0` — упрощает полигон через `shapely.simplify()`
- Graceful degradation: при shapely недоступен или геометрии вырождены → возвращает `[]`

**Параметры (`get_params_schema()`):**

| Параметр | Тип | Диапазон | Умолч. | Описание |
|----------|-----|----------|--------|----------|
| `buffer_width` | float | 0.001–0.10 | 0.008 | Ширина буфера (нормализованная к min(w,h)) |
| `cap_style` | select | round/flat/square | round | Форма торцов полилинии |
| `join_style` | select | round/mitre/bevel | round | Форма углов соединения |
| `simplify` | float | 0.0–0.01 | 0.001 | Допуск упрощения контура |

---

### Блок 2 — Tool Properties Panel

**`annotator/ui/panels/tool_props_panel.py`** — класс `ToolPropsPanel`:

- Расположение: под тулбаром, над холстом (фиксированная высота 36px)
- Скрыта по умолчанию; появляется только при активации инструмента с `get_params_schema()`
- Контролы рендерятся динамически из схемы:
  - `float` → `QDoubleSpinBox` (min/max/step/decimals из схемы)
  - `select` → `QComboBox` (options из схемы)
- Сигнал `params_changed(dict)` — эмитируется при любом изменении контрола
- `load_tool(tool)` — строит контролы из схемы текущего инструмента
- `clear_tool()` — скрывает панель

---

### Блок 3 — Интеграция в Main Window

**`annotator/ui/main_window.py`** (изменения):

| Добавлено | Описание |
|-----------|----------|
| `CrackTool` [C] | В тулбаре и меню Tools |
| `ToolPropsPanel` | Между тулбаром и холстом (показывается при активации Crack Tool) |
| `_on_tool_params_changed(params)` | Передаёт params в `active_tool.set_params()` |
| Layout | `self._view` обёрнут в center-виджет с VBoxLayout |

Логика показа панели в `_activate_tool()`:
```python
if hasattr(tool, "get_params_schema"):
    self._tool_props.load_tool(tool)
else:
    self._tool_props.clear_tool()
```

---

### Блок 4 — Регистрация инструмента

**`annotator/domain/label_class.py`**:

```python
ANNOTATION_TYPE_TOOLS = {
    "polygon": ["polygon", "crack_tool"],  # crack_tool добавлен
    ...
}
```

Класс с `annotation_type: polygon` теперь допускает оба инструмента.
`ANNOTATION_TYPE_DEFAULT_TOOL["polygon"]` остался `"polygon"` — crack_tool
активируется вручную через тулбар или горячую клавишу C.

---

### Блок 5 — Экспортная безопасность

`source_geometry` и `tool_params` хранятся внутри `ann.data`, но
все YOLO-экспортёры читают только те поля, которые им нужны:
- `yolo_seg.py` читает только `data["points"]`
- `yolo_detect.py` пропускает SEGMENT-аннотации
- `yolo_obb.py` пропускает SEGMENT-аннотации

Никакой дополнительной фильтрации не нужно — внутренние поля
**никогда не попадают в YOLO label-файлы**.

---

### Зависимости

| Пакет | Версия | Назначение |
|-------|--------|------------|
| `shapely` | ≥ 2.0.0 | Буферизация полилинии → полигон |

Добавлен в `requirements.txt`.

---

## Файлы Фазы 6

```
annotator/
  tools/
    crack_tool.py              (CrackTool — полилиния + буфер, горячая клавиша C)
  ui/
    panels/
      tool_props_panel.py      (ToolPropsPanel — динамические контролы из схемы)
    main_window.py             (+ CrackTool [C], ToolPropsPanel, _on_tool_params_changed)
  domain/
    label_class.py             (+ crack_tool в allowed_tools для polygon)

requirements.txt               (+ shapely>=2.0.0)
test_phase6.py                 (58/58 checks)
docs/
  phase6_completion_ru.md
```

---

## Команды запуска

```bat
cd new_annotator
run.bat                              :: запуск приложения
.venv\Scripts\pip install -r requirements.txt   :: установка зависимостей (включая shapely)
.venv\Scripts\python test_phase1.py  :: регрессия Фаз 1–3 (35/35)
.venv\Scripts\python test_phase4.py  :: регрессия Фазы 4 (29/29)
.venv\Scripts\python test_phase5.py  :: регрессия Фазы 5 (74/74)
.venv\Scripts\python test_phase6.py  :: тесты Фазы 6 (58/58)
```

---

## Шаги ручного тестирования

### 1. Crack Tool — базовый сценарий

1. Открыть проект, создать класс с `annotation_type: polygon`
2. Нажать **C** — активируется Crack Tool
3. Под тулбаром появляется Tool Properties Panel с 4 контролами
4. Кликать на изображении вдоль трещины — оранжевая пунктирная линия + полупрозрачный полигон
5. Двойной клик или Enter → аннотация зафиксирована
6. В панели Annotations — тип `segment`, инструмент `crack_tool`

### 2. Изменение параметров в реальном времени

1. Активировать Crack Tool, нажать несколько точек
2. Изменить **Buffer width** в Tool Properties Panel → полигон preview обновляется немедленно
3. Изменить **Cap style** на `flat` → торцы меняют форму
4. Enter → зафиксировать

### 3. Проверка Tool Properties Panel

1. Нажать **V** (Select) → Panel скрывается
2. Нажать **C** (Crack) → Panel появляется
3. Нажать **P** (Polygon) → Panel скрывается

### 4. Экспорт YOLO Segment

1. Нарисовать несколько crack-аннотаций
2. **File → Export Dataset…** → YOLO Segment → Export
3. Открыть `.txt` — только `class_id x1 y1 x2 y2 ...`
4. Убедиться что `source_geometry` и `tool_params` отсутствуют в файле

### 5. Сохранение и загрузка

1. Нарисовать crack-аннотацию
2. Ctrl+S — сохранить
3. Закрыть и открыть проект снова
4. Аннотация сохранена корректно, `source_geometry` и `tool_params` присутствуют во внутреннем формате

---

## Критерии приёмки

| Критерий | Статус |
|----------|--------|
| CrackTool рисует полилинию (клик=точка, Enter=финализация) | ✅ |
| Preview обновляется в реальном времени (линия + полигон) | ✅ |
| При изменении buffer_width preview перестраивается мгновенно | ✅ |
| Результат = SEGMENT-аннотация с буферным полигоном | ✅ |
| source_geometry хранится inline в ann.data | ✅ |
| tool_params хранятся inline в ann.data | ✅ |
| source_geometry сохраняется/загружается корректно | ✅ |
| YOLO label-файлы не содержат source_geometry/tool_params | ✅ |
| Tool Properties Panel появляется при активации Crack Tool | ✅ |
| Tool Properties Panel скрывается при переключении на другой инструмент | ✅ |
| Контролы Panel обновляют параметры инструмента в реальном времени | ✅ |
| crack_tool разрешён для классов с annotation_type=polygon | ✅ |
| Регрессия Фаз 1–3: 35/35 | ✅ |
| Регрессия Фазы 4: 29/29 | ✅ |
| Регрессия Фазы 5: 74/74 | ✅ |
| Тесты Фазы 6: 58/58 | ✅ |

---

## Известные ограничения

- **Нет редактирования source_geometry** — исходную полилинию нельзя изменить после создания аннотации. Для изменения — удалить и нарисовать заново.
- **Минимум 2 точки** — одиночный клик не создаёт аннотацию.
- **shapely обязателен** — без него `_buffer_polyline` возвращает `[]` и commit не выполняется. Установка через `pip install shapely`.

---

## Предложение для Фазы 7

| Направление | Описание |
|-------------|----------|
| Plugin loader | Автоматическая загрузка инструментов из `plugins/*.py` (см. §9 architecture-notes.md) |
| POSE / CLASSIFY | Инструменты и экспорт (YOLO pose format) |
| COCO export | JSON с атрибутами |
| Редактирование source_geometry | Режим "edit source line" для crack-аннотаций |
| Mask type | Pixel-mask через brush инструмент |
