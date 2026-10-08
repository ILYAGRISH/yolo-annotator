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
}


def t(key: str, **kw) -> str:
    table = _RU if current_language() == "RU" else _EN
    text = table.get(key, _EN.get(key, key))
    return text.format(**kw) if kw else text
