"""Minimal EN/RU localization.

Usage:
    from annotator.i18n import tr, set_language, current_language, load_saved

    tr("images")           → "Images" or "Изображения"
    set_language("RU")     → switches and saves to QSettings
    load_saved()           → reads saved choice on startup
"""
from __future__ import annotations

_LANG: str = "EN"

# ---------------------------------------------------------------------------
_EN: dict[str, str] = {
    # Panel headers
    "images":       "Images",
    "classes":      "Classes",
    "annotations":  "Annotations",

    # Images panel
    "search_placeholder": "Search by name…",
    "all_splits":   "All splits",
    "all_status":   "All",
    "annotated":    "Annotated",
    "unannotated":  "Unannotated",
    "images_hint":  "A / D — prev / next   RMB — set split\nDrag images or folders here to add",

    # Annotations panel
    "subclass_lbl":      "Subclass:",
    "btn_classify_img":  "+ Classify image",
    "btn_edit_src":      "Edit source",
    "btn_delete":        "Delete",

    # Classes panel
    "btn_schema":   "Schema…",

    # QC panel
    "btn_validate": "▶  Validate",
    "qc_stats":     "Statistics",
    "qc_no_data":   "No validation data  —  press Validate",
    "qc_no_issues": "✔  No issues found",

    # Main menus
    "menu_file":    "&File",
    "menu_edit":    "&Edit",
    "menu_schema":  "&Schema",
    "menu_qc":      "&QC",
    "menu_help":    "&Help",

    # File menu actions
    "act_new_project":      "&New Project…",
    "act_open_project":     "&Open Project…",
    "act_save_project":     "&Save Project",
    "act_close_project":    "&Close Project",
    "act_project_settings": "Project Settings…",
    "act_your_name":        "Your Name…",
    "act_add_images":       "Add Images from Folder…",
    "act_split_dataset":    "Split Dataset…",
    "act_import_dataset":   "Import Dataset…",
    "act_assign_images":    "Assign Images…",
    "act_export_dataset":   "Export Dataset…",
    "act_quit":             "&Quit",

    # Schema menu actions
    "act_edit_schema":   "Edit Class Schema…",
    "act_export_schema": "Export class_schema.json…",
    "act_import_schema": "Import class_schema.json…",

    # QC menu actions
    "act_validate":             "Validate Project",
    "act_export_report_json":   "Export Report (JSON)…",
    "act_export_report_csv":    "Export Report (CSV)…",

    # Help menu actions
    "act_about": "About…",

    # Tabs
    "tab_annotations": "Annotations",
    "tab_qc":          "QC",

    # Toolbar hint
    "toolbar_hint": (
        "  Polygon/Polyline/Crack/Pose: click=add · RMB=undo · dbl-click or Enter=finish · Esc=cancel   "
        "BBox/OBB: drag   Select: click=pick · drag handle=move vertex · Del=delete   "
        "Brush: drag=paint · Enter=commit · Esc=discard   "
        "Wheel=zoom · MMB=pan   A/D=prev/next"
    ),

    # Project settings dialog
    "dlg_project_settings": "Project Settings",
    "lbl_name":             "Name:",
    "grp_settings":         "Settings",
    "lbl_auto_export":      "Auto-export format:",
    "lbl_autosave":         "Autosave interval:",
    "grp_hotkeys":          "Hotkeys  (click a field, then press the desired key)",
    "hk_hint":              "Esc = cancel  ·  Backspace = clear (disable)",
    "grp_info":             "Info",
    "lbl_created":          "Created:",
    "lbl_modified":         "Modified:",
    "lbl_id":               "ID:",
}

_RU: dict[str, str] = {
    # Panel headers
    "images":       "Изображения",
    "classes":      "Классы",
    "annotations":  "Аннотации",

    # Images panel
    "search_placeholder": "Поиск по имени…",
    "all_splits":   "Все сплиты",
    "all_status":   "Все",
    "annotated":    "С аннотациями",
    "unannotated":  "Без аннотаций",
    "images_hint":  "A / D — пред / след   ПКМ — сплит\nПеретащите изображения или папки сюда",

    # Annotations panel
    "subclass_lbl":      "Подкласс:",
    "btn_classify_img":  "+ Метка изображения",
    "btn_edit_src":      "Ред. источник",
    "btn_delete":        "Удалить",

    # Classes panel
    "btn_schema":   "Схема…",

    # QC panel
    "btn_validate": "▶  Проверить",
    "qc_stats":     "Статистика",
    "qc_no_data":   "Нет данных  —  нажмите «Проверить»",
    "qc_no_issues": "✔  Проблем не найдено",

    # Main menus
    "menu_file":    "&Файл",
    "menu_edit":    "&Правка",
    "menu_schema":  "&Схема",
    "menu_qc":      "&КК",
    "menu_help":    "&Справка",

    # File menu actions
    "act_new_project":      "&Новый проект…",
    "act_open_project":     "&Открыть проект…",
    "act_save_project":     "&Сохранить",
    "act_close_project":    "&Закрыть проект",
    "act_project_settings": "Настройки проекта…",
    "act_your_name":        "Ваше имя…",
    "act_add_images":       "Добавить папку с изображениями…",
    "act_split_dataset":    "Разбить датасет…",
    "act_import_dataset":   "Импорт датасета…",
    "act_assign_images":    "Назначить изображения…",
    "act_export_dataset":   "Экспорт датасета…",
    "act_quit":             "&Выход",

    # Schema menu actions
    "act_edit_schema":   "Редактировать схему…",
    "act_export_schema": "Экспорт class_schema.json…",
    "act_import_schema": "Импорт class_schema.json…",

    # QC menu actions
    "act_validate":             "Проверить датасет",
    "act_export_report_json":   "Экспорт отчёта (JSON)…",
    "act_export_report_csv":    "Экспорт отчёта (CSV)…",

    # Help menu actions
    "act_about": "О программе…",

    # Tabs
    "tab_annotations": "Аннотации",
    "tab_qc":          "КК",

    # Toolbar hint
    "toolbar_hint": (
        "  Полигон/Полилиния/Трещина/Поза: клик=точка · ПКМ=отмена · 2×клик или Enter=завершить · Esc=отмена   "
        "BBox/OBB: тянуть   Выбор: клик=выбрать · тянуть=двигать · Del=удалить   "
        "Кисть: тянуть=рисовать · Enter=принять · Esc=отменить   "
        "Колесо=зум · ССК=пан   A/D=пред/след"
    ),

    # Project settings dialog
    "dlg_project_settings": "Настройки проекта",
    "lbl_name":             "Имя:",
    "grp_settings":         "Настройки",
    "lbl_auto_export":      "Авто-экспорт:",
    "lbl_autosave":         "Автосохранение:",
    "grp_hotkeys":          "Горячие клавиши  (кликните поле, затем нажмите клавишу)",
    "hk_hint":              "Esc = отмена  ·  Backspace = сбросить (отключить)",
    "grp_info":             "Информация",
    "lbl_created":          "Создан:",
    "lbl_modified":         "Изменён:",
    "lbl_id":               "ID:",
}

_STRINGS: dict[str, dict[str, str]] = {"EN": _EN, "RU": _RU}


def tr(key: str) -> str:
    """Return the UI string for *key* in the current language."""
    lang_dict = _STRINGS.get(_LANG, _EN)
    return lang_dict.get(key, _EN.get(key, key))


def current_language() -> str:
    return _LANG


def set_language(lang: str) -> None:
    global _LANG
    if lang not in _STRINGS:
        return
    _LANG = lang
    try:
        from PyQt6.QtCore import QSettings
        QSettings("Annotator", "App").setValue("language", lang)
    except Exception:
        pass


def load_saved() -> None:
    """Load language preference from QSettings (call once at startup)."""
    global _LANG
    try:
        from PyQt6.QtCore import QSettings
        saved = QSettings("Annotator", "App").value("language", "EN")
        if saved in _STRINGS:
            _LANG = saved
    except Exception:
        pass
