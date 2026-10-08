"""UI strings of the ML extension — kept here, not in annotator/i18n.py, so the
extension can be removed or changed without touching the app's dictionary.
Follows the app's current language."""
from __future__ import annotations

from annotator.i18n import current_language

_EN = {
    "menu_ml":            "&ML",
    "act_settings":       "ML Settings…",
    "act_restart":        "Restart ML Backend",
    "act_stop":           "Stop ML Backend",

    "st_stopped":         "ML: off",
    "st_starting":        "ML: starting…",
    "st_ready":           "ML: ready",
    "st_busy":            "ML: busy",
    "st_error":           "ML: error",
    "st_tip":             "ML backend — click for settings\nPython: {python}",
    "st_tip_none":        "(not configured)",

    "dlg_title":          "ML Settings",
    "grp_env":            "Python environment for ML",
    "env_intro":          "Models run in a separate process with its own Python (PyTorch, "
                          "Ultralytics), so the annotator itself stays light.",
    "env_placeholder":    "empty = {default}",
    "env_missing":        "No ML environment yet. Create it with setup_ml_env.bat "
                          "(downloads up to ~3 GB), or choose an existing Python "
                          "(a conda env with ultralytics also works).",
    "btn_browse":         "Browse…",
    "btn_check":          "Check",
    "checking":           "Checking… the first import of PyTorch can take 10–20 s.",
    "check_ok":           "The ML environment works.",
    "check_warn":         "The backend runs, but PyTorch / Ultralytics are missing — models will not load.",
    "chk_autostart":      "Start the ML backend together with the app",
    "pick_python":        "Choose Python interpreter",

    "grp_model":          "Test a YOLO model",
    "model_placeholder":  "path to a .pt model",
    "btn_load":           "Load",
    "pick_model":         "Choose a YOLO model",
    "loading":            "Loading model…",
    "model_ok":           "Task: {task}   ·   {n} classes   ·   {device}   ·   {sec} s{cached}",
    "model_cached":       "  (cached)",

    "grp_log":            "Backend log",
    "error":              "Error",

    # pre-labelling
    "act_prelabel_image":   "Pre-label Current Image",
    "act_prelabel_dataset": "Pre-label Dataset…",
    "act_remove_model":     "Remove Model Annotations…",
    "pl_title":           "Pre-label with a YOLO model",
    "pl_grp_model":       "Model",
    "pl_grp_mapping":     "Classes: model → project",
    "pl_col_model":       "Model class",
    "pl_col_project":     "Project class",
    "pl_skip":            "— skip —",
    "pl_create":          "+ new class «{name}» ({type})",
    "pl_filter":          "Search model classes…",
    "pl_btn_create":      "Create all missing",
    "pl_create_tip":      "Every model class in the list that is “skip” or “+ new class” becomes "
                          "a project class now (with a search, only the classes found)",
    "pl_btn_create_sel":  "Create selected",
    "pl_create_sel_tip":  "Creates the classes marked “+ new class” in their rows",
    "pl_mark_first":      "First choose “+ new class” in the rows of the model classes you need.",
    "pl_marked":          " · to create: {n}",
    "pl_taken":           "already chosen for other model classes:",
    "pl_nothing_missing": "Nothing to create: these model classes are already mapped.",
    "pl_confirm_create":  "Create {n} classes in the project?",
    "pl_created":         "Classes created: {n}.",
    "pl_placeholder":     " The empty default class «{name}» was replaced.",
    "pl_mapped":          "{n} of {total} model classes mapped",
    "pl_grp_params":      "Parameters",
    "pl_conf":            "Confidence ≥",
    "pl_iou":             "Overlap (IoU) ≤",
    "pl_imgsz":           "Image size",
    "pl_auto":            "model default",
    "pl_simplify":        "Polygon simplification, px",
    "pl_grp_images":      "Images",
    "pl_scope_all":       "All images",
    "pl_scope_split":     "Split: {split}",
    "pl_count":           "{n} images",
    "pl_existing":        "Images that already have annotations:",
    "pl_ex_skip":         "skip them",
    "pl_ex_replace":      "replace earlier model annotations (manual ones are kept)",
    "pl_ex_add":          "add to existing annotations",
    "pl_btn_current":     "Current image",
    "pl_btn_run":         "Run on {n} images",
    "pl_btn_stop":        "Stop",
    "pl_btn_close":       "Close",
    "pl_load_first":      "Load a model first.",
    "pl_running":         "{done} / {total}  ·  {name}",
    "pl_done":            "Done in {sec} s: {processed} images processed, {added} annotations added",
    "pl_replaced":        ", {n} earlier model annotations replaced",
    "pl_skipped_existing": "{n} images skipped (already annotated)",
    "pl_failed":          "{n} images failed",
    "pl_cancelled":       "Stopped by the user.",
    "pl_not_counted":     "Not added: {reasons}",
    "pl_no_images":       "No images to process.",
    "pl_no_project":      "Open a project first.",
    "pl_no_image":        "Select an image first.",
    "pl_not_allowed":     "This image is not assigned to you.",
    "pl_quick_done":      "Pre-label ({model}): +{n} annotations in {sec} s",
    "pl_quick_busy":      "Pre-labelling is already running…",
    "rm_title":           "Remove model annotations",
    "rm_text":            "Annotations made by a model (🤖): {cur} on this image, {all} in all your images.\n"
                          "Manual annotations are never touched.",
    "rm_current":         "This image",
    "rm_all":             "All images",
    "rm_done":            "Removed {n} model annotations",
    "rm_none":            "No model annotations found.",
}

_RU = {
    "menu_ml":            "&ML",
    "act_settings":       "Настройки ML…",
    "act_restart":        "Перезапустить ML-сервер",
    "act_stop":           "Остановить ML-сервер",

    "st_stopped":         "ML: выкл",
    "st_starting":        "ML: запуск…",
    "st_ready":           "ML: готов",
    "st_busy":            "ML: занят",
    "st_error":           "ML: ошибка",
    "st_tip":             "ML-сервер — нажмите, чтобы открыть настройки\nPython: {python}",
    "st_tip_none":        "(не настроен)",

    "dlg_title":          "Настройки ML",
    "grp_env":            "Python-окружение для ML",
    "env_intro":          "Модели работают в отдельном процессе со своим Python (PyTorch, "
                          "Ultralytics), поэтому сама программа разметки остаётся лёгкой.",
    "env_placeholder":    "пусто = {default}",
    "env_missing":        "ML-окружения ещё нет. Создайте его скриптом setup_ml_env.bat "
                          "(скачает до ~3 ГБ) или выберите готовый Python "
                          "(подойдёт и conda-окружение с ultralytics).",
    "btn_browse":         "Обзор…",
    "btn_check":          "Проверить",
    "checking":           "Проверка… первый импорт PyTorch может занять 10–20 с.",
    "check_ok":           "ML-окружение работает.",
    "check_warn":         "Сервер запускается, но нет PyTorch / Ultralytics — модели не загрузятся.",
    "chk_autostart":      "Запускать ML-сервер вместе с программой",
    "pick_python":        "Выберите интерпретатор Python",

    "grp_model":          "Проверить YOLO-модель",
    "model_placeholder":  "путь к модели .pt",
    "btn_load":           "Загрузить",
    "pick_model":         "Выберите YOLO-модель",
    "loading":            "Загрузка модели…",
    "model_ok":           "Задача: {task}   ·   классов: {n}   ·   {device}   ·   {sec} с{cached}",
    "model_cached":       "  (из кэша)",

    "grp_log":            "Журнал сервера",
    "error":              "Ошибка",

    # предразметка
    "act_prelabel_image":   "Разметить текущее изображение моделью",
    "act_prelabel_dataset": "Разметить датасет моделью…",
    "act_remove_model":     "Удалить разметку модели…",
    "pl_title":           "Предразметка YOLO-моделью",
    "pl_grp_model":       "Модель",
    "pl_grp_mapping":     "Классы: модель → проект",
    "pl_col_model":       "Класс модели",
    "pl_col_project":     "Класс проекта",
    "pl_skip":            "— пропустить —",
    "pl_create":          "+ новый класс «{name}» ({type})",
    "pl_filter":          "Поиск класса модели…",
    "pl_btn_create":      "Создать все недостающие",
    "pl_create_tip":      "Все классы модели в списке с «пропустить» или «+ новый класс» сразу станут "
                          "классами проекта (при поиске — только найденные)",
    "pl_btn_create_sel":  "Создать выбранные",
    "pl_create_sel_tip":  "Создаёт классы, отмеченные «+ новый класс» в своих строках",
    "pl_mark_first":      "Сначала выберите «+ новый класс» в строках нужных классов модели.",
    "pl_marked":          " · к созданию: {n}",
    "pl_taken":           "уже выбраны для других классов модели:",
    "pl_nothing_missing": "Создавать нечего: эти классы модели уже сопоставлены.",
    "pl_confirm_create":  "Создать в проекте классов: {n}?",
    "pl_created":         "Создано классов: {n}.",
    "pl_placeholder":     " Пустой класс по умолчанию «{name}» заменён.",
    "pl_mapped":          "Сопоставлено {n} из {total} классов модели",
    "pl_grp_params":      "Параметры",
    "pl_conf":            "Уверенность ≥",
    "pl_iou":             "Перекрытие (IoU) ≤",
    "pl_imgsz":           "Размер изображения",
    "pl_auto":            "как у модели",
    "pl_simplify":        "Упрощение полигонов, пикс.",
    "pl_grp_images":      "Изображения",
    "pl_scope_all":       "Все изображения",
    "pl_scope_split":     "Сплит: {split}",
    "pl_count":           "изображений: {n}",
    "pl_existing":        "Изображения, где уже есть разметка:",
    "pl_ex_skip":         "пропускать",
    "pl_ex_replace":      "заменять прежнюю разметку модели (ручная сохраняется)",
    "pl_ex_add":          "добавлять к имеющейся разметке",
    "pl_btn_current":     "Текущее изображение",
    "pl_btn_run":         "Разметить {n} изобр.",
    "pl_btn_stop":        "Остановить",
    "pl_btn_close":       "Закрыть",
    "pl_load_first":      "Сначала загрузите модель.",
    "pl_running":         "{done} / {total}  ·  {name}",
    "pl_done":            "Готово за {sec} с: обработано изображений — {processed}, добавлено аннотаций — {added}",
    "pl_replaced":        ", заменено прежних аннотаций модели — {n}",
    "pl_skipped_existing": "Пропущено изображений с разметкой: {n}",
    "pl_failed":          "Ошибок на изображениях: {n}",
    "pl_cancelled":       "Остановлено пользователем.",
    "pl_not_counted":     "Не добавлено: {reasons}",
    "pl_no_images":       "Нет изображений для разметки.",
    "pl_no_project":      "Сначала откройте проект.",
    "pl_no_image":        "Сначала выберите изображение.",
    "pl_not_allowed":     "Это изображение вам не назначено.",
    "pl_quick_done":      "Предразметка ({model}): +{n} аннотаций за {sec} с",
    "pl_quick_busy":      "Предразметка уже идёт…",
    "rm_title":           "Удалить разметку модели",
    "rm_text":            "Аннотаций, сделанных моделью (🤖): на этом изображении — {cur}, во всех ваших изображениях — {all}.\n"
                          "Ручная разметка не затрагивается.",
    "rm_current":         "Это изображение",
    "rm_all":             "Все изображения",
    "rm_done":            "Удалено аннотаций модели: {n}",
    "rm_none":            "Аннотаций модели не найдено.",
}


# skip reasons reported by convert.py (English text is the key)
_REASONS_RU = {
    "class not mapped":         "класс не сопоставлен",
    "incompatible class type":  "неподходящий тип класса",
    "empty geometry":           "пустая геометрия",
    "no project folder for masks": "нет папки проекта для масок",
    "keypoint count differs from the class skeleton": "число точек отличается от скелета класса",
    "no visible keypoints":     "нет видимых точек",
    "already labelled":         "метка уже есть",
    "below confidence":         "уверенность ниже порога",
}


def reason(text: str) -> str:
    return _REASONS_RU.get(text, text) if current_language() == "RU" else text


def t(key: str, **kw) -> str:
    table = _RU if current_language() == "RU" else _EN
    text = table.get(key, _EN.get(key, key))
    return text.format(**kw) if kw else text
