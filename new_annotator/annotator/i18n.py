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
    "menu_recent":          "Open &Recent",
    "act_clear_recent":     "Clear List",
    "recent_empty":         "(no recent projects)",
    "recent_missing_title": "Project not found",
    "recent_missing_text":  "The project folder no longer exists or is not available:\n{path}\n\nIt has been removed from the recent list.",
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
    # Review of model annotations (Phase 8-A)
    "menu_review":           "&Review",
    "act_review_accept":     "Accept selected annotation",
    "act_review_accept_all": "Accept all on image  →  next",
    "act_review_next":       "Next image to review",
    "act_review_unmark":     "Mark selected as unreviewed",
    "status_unreviewed":     "🤖 Unreviewed",
    "unreviewed_n":          "{n} unreviewed",
    "reviewed_tip":          "Reviewed",
    "unreviewed_tip":        "Not reviewed  —  R accepts, editing accepts too",
    "review_accepted":       "Accepted: {n}",
    "review_select_first":   "Select a 🤖 annotation first (Shift+R accepts the whole image)",
    "review_nothing":        "No unreviewed 🤖 annotations on this image",
    "review_unmarked":       "Marked as unreviewed: {n}",
    "review_all_done":       "No unreviewed 🤖 annotations left among the listed images",
    # Video and tracks (Phase 8-B)
    "menu_video":            "&Video",
    "act_import_video":      "Import Video…",
    "act_track_start":       "Start Track from Selected",
    "act_track_keyframe":    "Keyframe of Active Track Here",
    "act_track_prev_key":    "Previous Keyframe",
    "act_track_next_key":    "Next Keyframe",
    "act_track_delete":      "Delete Active Track…",
    "track_select_first":    "Select an annotation first (box, OBB, polygon, point or pose)",
    "track_not_video":       "Tracks work on video frames — File › Import Video…",
    "track_not_trackable":   "Brush masks, semantic layers and image labels can't be tracked",
    "track_already":         "This annotation already belongs to a track — it is now the active one",
    "track_started":         "Track started. Go to a later frame and press Shift+T to add a keyframe",
    "track_none_active":     "No active track — select an annotation of a track (or press T on one)",
    "track_already_key":     "This frame already holds a keyframe of the track",
    "track_key_added":       "Keyframe added — move it onto the object; frames in between are interpolated",
    "track_delete_q":        "Delete track #{id} on all its {n} frames?",
    "track_deleted":         "Track #{id}: {n} annotations deleted",
    "tl_prev_key":           "Previous keyframe of the active track (Shift+A)",
    "tl_prev":               "Previous frame (A)",
    "tl_next":               "Next frame (D)",
    "tl_next_key":           "Next keyframe of the active track (Shift+D)",
    "tl_bar_tip":            "Click or drag to go to a frame. Grey — frames with annotations, colour — the active track, ◆ — its keyframes",
    "tl_frame":              "frame {f}",
    "tl_no_track":           "no active track (T — start one)",
    "tl_track":              "Track #{id} {cls}  ·  ◆ {keys}",
    "vid_title":             "Import Video",
    "vid_browse":            "Browse…",
    "vid_file":              "Video:",
    "vid_step":              "Take every:",
    "vid_step_suffix":       " th frame",
    "vid_sec":               " s",
    "vid_range":             "From — to:",
    "vid_folder":            "Frames folder:",
    "vid_hint":              "Frames are saved as JPEG images and added to the project like any other image — all tools, SAM and pre-labelling work on them. Neighbouring frames are nearly identical: for a dataset 2–5 frames per second is usually plenty.",
    "vid_import":            "Import",
    "vid_stop":              "Stop",
    "vid_filter":            "Videos",
    "vid_cannot_open":       "Can't open the video:\n{path}",
    "vid_about":             "{w}×{h}, {fps:.2f} fps, {n} frames, {dur:.1f} s",
    "vid_estimate":          "≈ {n} frames ({fps:.2f} per second of video)",
    "vid_no_frames":         "No frames were extracted.",
    # Time events on video (Phase 8-D)
    "tab_events":            "Events",
    "act_event_mark":        "Event Start / End Here",
    "act_event_cancel":      "Cancel Started Event",
    "act_event_edit":        "Edit Selected Event…",
    "act_event_delete":      "Delete Selected Event",
    "act_event_prev":        "Previous Event",
    "act_event_next":        "Next Event",
    "act_event_types":       "Event Types…",
    "ev_not_video":          "Events are marked on video frames — File › Import Video…",
    "ev_started":            "Event started. Go to its last frame and press E again (Shift+E — cancel)",
    "ev_started_track":      "Event about object #{id} started. Go to its last frame and press E again (Shift+E — cancel)",
    "ev_added":              "Event added",
    "ev_cancelled":          "Started event cancelled",
    "ev_no_types":           "Create an event type first",
    "ev_select_first":       "Select an event first (Events tab or the event strip)",
    "ev_type":               "Event:",
    "ev_type_tip":           "Type for new events (E — start / end)",
    "ev_new_type":           "+ New event type…",
    "ev_open":               "● event from frame {f}  —  E on the last frame, Shift+E cancels",
    "ev_summary":            "events: {n}",
    "ev_here":               "here: {names}",
    "ev_bar_tip":            "Time events of this video. Click — select an event, double click — edit it. E — start / end a new one",
    "ev_frames":             "frames {a}–{b}",
    "ev_col_type":           "Type",
    "ev_col_frames":         "Frames",
    "ev_col_time":           "Time",
    "ev_col_track":          "Track",
    "ev_col_note":           "Note",
    "ev_btn_edit":           "Edit…",
    "ev_btn_delete":         "Delete",
    "ev_btn_start":          "⇤ Start here",
    "ev_btn_end":            "End here ⇥",
    "ev_btn_start_tip":      "The selected event starts on the current frame",
    "ev_btn_end_tip":        "The selected event ends on the current frame",
    "ev_btn_types":          "Types…",
    "ev_hint":               "E — start an event on this frame, E again on its last frame — finish it. Shift+E — cancel. Double click — go to the event. Ctrl+Z undoes while you stay on the frame.",
    "ev_no_video":           "Not a video frame. Import a video (File › Import Video…) to mark time events.",
    "ev_head":               "🎞 {video}  ·  events: {n}",
    "ev_dlg_title":          "Event",
    "ev_first":              "First frame:",
    "ev_last":               "Last frame:",
    "ev_here_btn":           "Current",
    "ev_here_btn_tip":       "The frame shown now",
    "ev_no_track":           "— no object —",
    "ev_new_type_title":     "New event type",
    "ev_new_type_prompt":    "Name (e.g. lane change, fall, goal):",
    "ev_types_title":        "Event Types",
    "ev_types_hint":         "Types are shared by all videos of the project. Changes apply at once.",
    "ev_types_add":          "Add…",
    "ev_types_rename":       "Rename…",
    "ev_types_color":        "Colour…",
    "ev_types_delete":       "Delete",
    "ev_types_delete_q":     "Delete type \"{name}\" and its {n} events in all videos? This can't be undone.",
    "ev_types_delete_q0":    "Delete type \"{name}\"?",
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
    "menu_recent":          "Открыть &недавние",
    "act_clear_recent":     "Очистить список",
    "recent_empty":         "(нет недавних проектов)",
    "recent_missing_title": "Проект не найден",
    "recent_missing_text":  "Папка проекта больше не существует или недоступна:\n{path}\n\nПроект убран из списка недавних.",
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
    # Приёмка предразметки (фаза 8-A)
    "menu_review":           "&Приёмка",
    "act_review_accept":     "Принять выделенную аннотацию",
    "act_review_accept_all": "Принять все на изображении  →  следующее",
    "act_review_next":       "Следующее изображение для приёмки",
    "act_review_unmark":     "Вернуть выделенную в непроверенные",
    "status_unreviewed":     "🤖 Не проверено",
    "unreviewed_n":          "не проверено: {n}",
    "reviewed_tip":          "Проверено",
    "unreviewed_tip":        "Не проверено  —  R принимает, правка тоже принимает",
    "review_accepted":       "Принято: {n}",
    "review_select_first":   "Сначала выделите 🤖-аннотацию (Shift+R принимает всё изображение)",
    "review_nothing":        "На этом изображении нет непроверенных 🤖-аннотаций",
    "review_unmarked":       "Возвращено в непроверенные: {n}",
    "review_all_done":       "Среди показанных изображений непроверенных 🤖-аннотаций не осталось",
    # Видео и треки (фаза 8-B)
    "menu_video":            "&Видео",
    "act_import_video":      "Импорт видео…",
    "act_track_start":       "Начать трек из выделенной",
    "act_track_keyframe":    "Ключевой кадр активного трека здесь",
    "act_track_prev_key":    "Предыдущий ключевой кадр",
    "act_track_next_key":    "Следующий ключевой кадр",
    "act_track_delete":      "Удалить активный трек…",
    "track_select_first":    "Сначала выделите аннотацию (рамка, OBB, полигон, точка или поза)",
    "track_not_video":       "Треки работают на кадрах видео — Файл › Импорт видео…",
    "track_not_trackable":   "Маски кистью, семантические слои и метки изображения в трек не превращаются",
    "track_already":         "Эта аннотация уже входит в трек — он стал активным",
    "track_started":         "Трек начат. Перейдите на кадр позже и нажмите Shift+T — ключевой кадр",
    "track_none_active":     "Нет активного трека — выделите аннотацию трека (или нажмите T на аннотации)",
    "track_already_key":     "На этом кадре уже есть ключевой кадр трека",
    "track_key_added":       "Ключевой кадр добавлен — передвиньте его на объект; кадры между ключевыми интерполируются",
    "track_delete_q":        "Удалить трек #{id} на всех его кадрах ({n})?",
    "track_deleted":         "Трек #{id}: удалено аннотаций — {n}",
    "tl_prev_key":           "Предыдущий ключевой кадр активного трека (Shift+A)",
    "tl_prev":               "Предыдущий кадр (A)",
    "tl_next":               "Следующий кадр (D)",
    "tl_next_key":           "Следующий ключевой кадр активного трека (Shift+D)",
    "tl_bar_tip":            "Клик или протяжка — переход к кадру. Серым — кадры с разметкой, цветом — активный трек, ◆ — его ключевые кадры",
    "tl_frame":              "кадр {f}",
    "tl_no_track":           "нет активного трека (T — начать)",
    "tl_track":              "Трек #{id} {cls}  ·  ◆ {keys}",
    "vid_title":             "Импорт видео",
    "vid_browse":            "Обзор…",
    "vid_file":              "Видео:",
    "vid_step":              "Брать каждый:",
    "vid_step_suffix":       "-й кадр",
    "vid_sec":               " с",
    "vid_range":             "С — по:",
    "vid_folder":            "Папка для кадров:",
    "vid_hint":              "Кадры сохраняются как JPEG и добавляются в проект как обычные изображения — на них работают все инструменты, SAM и предразметка. Соседние кадры почти одинаковы: для датасета обычно хватает 2–5 кадров на секунду видео.",
    "vid_import":            "Импортировать",
    "vid_stop":              "Стоп",
    "vid_filter":            "Видео",
    "vid_cannot_open":       "Не удаётся открыть видео:\n{path}",
    "vid_about":             "{w}×{h}, {fps:.2f} к/с, {n} кадров, {dur:.1f} с",
    "vid_estimate":          "≈ {n} кадров ({fps:.2f} на секунду видео)",
    "vid_no_frames":         "Не удалось извлечь ни одного кадра.",
    # События по времени (фаза 8-D)
    "tab_events":            "События",
    "act_event_mark":        "Начало / конец события здесь",
    "act_event_cancel":      "Отменить начатое событие",
    "act_event_edit":        "Изменить выбранное событие…",
    "act_event_delete":      "Удалить выбранное событие",
    "act_event_prev":        "Предыдущее событие",
    "act_event_next":        "Следующее событие",
    "act_event_types":       "Типы событий…",
    "ev_not_video":          "События отмечаются на кадрах видео — Файл › Импорт видео…",
    "ev_started":            "Событие начато. Перейдите на его последний кадр и снова нажмите E (Shift+E — отмена)",
    "ev_started_track":      "Событие объекта #{id} начато. Перейдите на его последний кадр и снова нажмите E (Shift+E — отмена)",
    "ev_added":              "Событие добавлено",
    "ev_cancelled":          "Начатое событие отменено",
    "ev_no_types":           "Сначала создайте тип события",
    "ev_select_first":       "Сначала выберите событие (вкладка «События» или полоса событий)",
    "ev_type":               "Событие:",
    "ev_type_tip":           "Тип для новых событий (E — начало / конец)",
    "ev_new_type":           "+ Новый тип события…",
    "ev_open":               "● событие с кадра {f}  —  E на последнем кадре, Shift+E — отмена",
    "ev_summary":            "событий: {n}",
    "ev_here":               "здесь: {names}",
    "ev_bar_tip":            "События этого видео. Клик — выбрать событие, двойной клик — изменить. E — начать / закончить новое",
    "ev_frames":             "кадры {a}–{b}",
    "ev_col_type":           "Тип",
    "ev_col_frames":         "Кадры",
    "ev_col_time":           "Время",
    "ev_col_track":          "Трек",
    "ev_col_note":           "Заметка",
    "ev_btn_edit":           "Изменить…",
    "ev_btn_delete":         "Удалить",
    "ev_btn_start":          "⇤ Начало здесь",
    "ev_btn_end":            "Конец здесь ⇥",
    "ev_btn_start_tip":      "Выбранное событие начинается на текущем кадре",
    "ev_btn_end_tip":        "Выбранное событие заканчивается на текущем кадре",
    "ev_btn_types":          "Типы…",
    "ev_hint":               "E — начать событие на этом кадре, E ещё раз на последнем кадре — закончить. Shift+E — отмена. Двойной клик — перейти к событию. Ctrl+Z отменяет, пока вы на том же кадре.",
    "ev_no_video":           "Это не кадр видео. Импортируйте видео (Файл › Импорт видео…), чтобы отмечать события.",
    "ev_head":               "🎞 {video}  ·  событий: {n}",
    "ev_dlg_title":          "Событие",
    "ev_first":              "Первый кадр:",
    "ev_last":               "Последний кадр:",
    "ev_here_btn":           "Текущий",
    "ev_here_btn_tip":       "Кадр, который сейчас на экране",
    "ev_no_track":           "— без объекта —",
    "ev_new_type_title":     "Новый тип события",
    "ev_new_type_prompt":    "Название (например: перестроение, падение, гол):",
    "ev_types_title":        "Типы событий",
    "ev_types_hint":         "Типы общие для всех видео проекта. Изменения применяются сразу.",
    "ev_types_add":          "Добавить…",
    "ev_types_rename":       "Переименовать…",
    "ev_types_color":        "Цвет…",
    "ev_types_delete":       "Удалить",
    "ev_types_delete_q":     "Удалить тип «{name}» и его события ({n}) во всех видео? Отменить будет нельзя.",
    "ev_types_delete_q0":    "Удалить тип «{name}»?",
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
        from annotator.app_settings import app_settings
        app_settings().setValue("language", lang)
    except Exception:
        pass


def load_saved() -> None:
    """Load language preference from QSettings (call once at startup)."""
    global _LANG
    try:
        from annotator.app_settings import app_settings
        saved = app_settings().value("language", "EN")
        if saved in _STRINGS:
            _LANG = saved
    except Exception:
        pass
