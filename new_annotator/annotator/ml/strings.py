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
    "act_sam":              "SAM — Label by Clicking",
    "act_sam_boxes":        "Boxes → Outlines with SAM…",
    "sb_title":           "Boxes → outlines with SAM",
    "sb_intro":           "Every box of the chosen class becomes an outline drawn by SAM: a polygon, a "
                          "brush mask or a tight rotated box of the target class. Works for boxes "
                          "drawn by hand and for detector pre-labels. Boxes already outlined are "
                          "skipped on the next run.",
    "sb_grp_classes":     "Classes",
    "sb_source":          "Boxes of class",
    "sb_target":          "→ outlines into class",
    "sb_new_class":       "+ new class «{name}» ({type})",
    "sb_delete":          "Delete the boxes that were outlined",
    "sb_grp_model":       "SAM model",
    "sb_scope_current":   "Current image",
    "sb_run":             "Outline",
    "sb_no_source":       "The project has no bbox or OBB class — nothing to outline.",
    "sb_done":            "Done in {sec} s: {images} images with boxes, {n} outlines added",
    "sb_removed":         ", {n} boxes deleted",
    "sb_empty":           "SAM found nothing in {n} boxes (they stay as they are).",
    "sb_nothing":         "No boxes of this class to outline (or all are outlined already).",
    "tool_sam":             "✧ SAM",
    "sam_tip":              "SAM [I]: click an object → mask. Left click — object, right click (after it) — "
                            "remove a wrongly included part, drag — a box around it. Enter — accept into the "
                            "current class, Backspace — undo the last click, Esc — clear.",
    "sam_hint":             "SAM: left click — object · right click — remove a part from the mask · drag — box · "
                            "Enter — accept · Backspace — undo click · Esc — clear",
    "sam_grp":              "SAM — labelling by clicks",
    "sam_intro":            "Segment Anything model for the SAM tool [I]. Recommended: "
                            "sam2.1_b.pt (accurate) or sam2.1_t.pt (faster, also fine on a CPU). "
                            "Download (one file): github.com/ultralytics/assets/releases — "
                            "or in the ML environment: python -c \"from ultralytics.utils.downloads "
                            "import attempt_download_asset as d; d('sam2.1_b.pt')\"",
    "sam_placeholder":      "Path to a SAM model (.pt), e.g. D:\\Models\\sam2.1_b.pt",
    "sam_pick":             "Choose a SAM model (sam2.1_b.pt, sam2.1_t.pt, mobile_sam.pt…)",
    "sam_load_ok":          "SAM ready   ·   {device}   ·   {sec} s{cached}",
    "sam_no_model":         "SAM: choose a SAM model (ML → ML Settings…)",
    "sam_no_image":         "SAM: open an image first",
    "sam_no_class":         "SAM: choose a class first",
    "sam_bad_class":        "SAM: a «{type}» class can't be filled from a mask — choose a "
                            "polygon, mask, box, OBB or point class",
    "sam_busy":             "SAM: thinking…",
    "sam_preparing":        "SAM: preparing the image…",
    "sam_ready":            "SAM ready — click the object",
    "sam_result":           "SAM: score {score:.2f} · {ms:.0f} ms — Enter to accept",
    "sam_empty":            "SAM found nothing here — add a point or draw a box",
    "sam_nothing":          "SAM: nothing to accept yet",
    "sam_need_positive":    "SAM: right click only removes parts from a mask — first left-click "
                            "the object (or drag a box around it)",
    "sam_wait":             "SAM: wait for the mask to update",
    "sam_added":            "SAM: added to «{name}»",
    "sam_error":            "SAM error ({kind}): {message}",
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
    "pl_ex_replace":      "replace earlier unreviewed model annotations (manual and accepted ones are kept)",
    "pl_ex_add":          "add to existing annotations",
    "pl_btn_current":     "Current image",
    "pl_btn_run":         "Run on {n} images",
    "pl_btn_stop":        "Stop",
    "pl_btn_close":       "Close",
    "pl_load_first":      "Load a model first.",
    "pl_running":         "{done} / {total}  ·  {name}",
    "pl_done":            "Done in {sec} s: {processed} images processed, {added} annotations added",
    "pl_replaced":        ", {n} earlier model annotations replaced",
    "pl_sam_outlined":    ", {n} of them outlined by SAM",
    "pl_sam_refine":      "Outlines via SAM",
    "pl_sam_hint":        "A detector fills polygon / mask / OBB classes with plain rectangles — "
                          "turn on «Outlines via SAM» to get real outlines.",
    "pl_sam_refine_tip":  "Detector models only: the boxes that go into polygon, mask or OBB classes "
                          "are outlined by SAM (the model in ML Settings) — real outlines and tight "
                          "rotated boxes instead of rectangles. Slower: one more SAM pass per image.",
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
    "rm_text":            "Unreviewed annotations made by a model (🤖): {cur} on this image, {all} in all your images.\n"
                          "Manual and accepted (✓🤖) annotations are never touched.",
    "rm_current":         "This image",
    "rm_all":             "All images",
    "rm_done":            "Removed {n} model annotations",
    "rm_none":            "No unreviewed model annotations found.",
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
    "act_sam":              "SAM — разметка кликом",
    "act_sam_boxes":        "Рамки → контуры через SAM…",
    "sb_title":           "Рамки → контуры через SAM",
    "sb_intro":           "Каждая рамка выбранного класса превращается в контур, проведённый SAM: "
                          "полигон, маску кистью или плотную повёрнутую рамку целевого класса. "
                          "Подходит и для рамок, нарисованных вручную, и для предразметки детектором. "
                          "Уже обведённые рамки при повторном запуске пропускаются.",
    "sb_grp_classes":     "Классы",
    "sb_source":          "Рамки класса",
    "sb_target":          "→ контуры в класс",
    "sb_new_class":       "+ новый класс «{name}» ({type})",
    "sb_delete":          "Удалить обведённые рамки",
    "sb_grp_model":       "Модель SAM",
    "sb_scope_current":   "Текущее изображение",
    "sb_run":             "Обвести",
    "sb_no_source":       "В проекте нет класса bbox или obb — обводить нечего.",
    "sb_done":            "Готово за {sec} с: изображений с рамками — {images}, добавлено контуров — {n}",
    "sb_removed":         ", удалено рамок — {n}",
    "sb_empty":           "В {n} рамках SAM ничего не нашёл (они остались как есть).",
    "sb_nothing":         "Рамок этого класса для обводки нет (или все уже обведены).",
    "tool_sam":             "✧ SAM",
    "sam_tip":              "SAM [I]: клик по объекту → маска. Левый клик — объект, правый (после него) — "
                            "убрать лишнее, попавшее в маску, протянуть — рамка вокруг объекта. Enter — принять в "
                            "текущий класс, Backspace — отменить последний клик, Esc — сбросить.",
    "sam_hint":             "SAM: ЛКМ — объект · ПКМ — убрать лишнее из маски · протянуть — рамка · "
                            "Enter — принять · Backspace — отменить клик · Esc — сбросить",
    "sam_grp":              "SAM — разметка кликами",
    "sam_intro":            "Модель Segment Anything для инструмента SAM [I]. Рекомендуется "
                            "sam2.1_b.pt (точнее) или sam2.1_t.pt (быстрее, годится и для CPU). "
                            "Скачать (один файл): github.com/ultralytics/assets/releases — "
                            "или в ML-окружении: python -c \"from ultralytics.utils.downloads "
                            "import attempt_download_asset as d; d('sam2.1_b.pt')\"",
    "sam_placeholder":      "Путь к модели SAM (.pt), например D:\\Models\\sam2.1_b.pt",
    "sam_pick":             "Выберите модель SAM (sam2.1_b.pt, sam2.1_t.pt, mobile_sam.pt…)",
    "sam_load_ok":          "SAM готов   ·   {device}   ·   {sec} с{cached}",
    "sam_no_model":         "SAM: выберите модель SAM (ML → Настройки ML…)",
    "sam_no_image":         "SAM: сначала откройте изображение",
    "sam_no_class":         "SAM: сначала выберите класс",
    "sam_bad_class":        "SAM: класс типа «{type}» нельзя заполнить маской — выберите класс "
                            "polygon, mask, bbox, obb или point",
    "sam_busy":             "SAM: считаю…",
    "sam_preparing":        "SAM: подготовка изображения…",
    "sam_ready":            "SAM готов — кликните по объекту",
    "sam_result":           "SAM: качество {score:.2f} · {ms:.0f} мс — Enter, чтобы принять",
    "sam_empty":            "SAM ничего не нашёл — добавьте точку или обведите рамкой",
    "sam_nothing":          "SAM: принимать пока нечего",
    "sam_need_positive":    "SAM: правый клик только убирает лишнее из маски — сначала левый "
                            "клик по объекту (или рамка вокруг него)",
    "sam_wait":             "SAM: подождите, маска обновляется",
    "sam_added":            "SAM: добавлено в «{name}»",
    "sam_error":            "Ошибка SAM ({kind}): {message}",
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
    "pl_ex_replace":      "заменять прежнюю непроверенную разметку модели (ручная и принятая сохраняются)",
    "pl_ex_add":          "добавлять к имеющейся разметке",
    "pl_btn_current":     "Текущее изображение",
    "pl_btn_run":         "Разметить {n} изобр.",
    "pl_btn_stop":        "Остановить",
    "pl_btn_close":       "Закрыть",
    "pl_load_first":      "Сначала загрузите модель.",
    "pl_running":         "{done} / {total}  ·  {name}",
    "pl_done":            "Готово за {sec} с: обработано изображений — {processed}, добавлено аннотаций — {added}",
    "pl_replaced":        ", заменено прежних аннотаций модели — {n}",
    "pl_sam_outlined":    ", из них обведено SAM — {n}",
    "pl_sam_refine":      "Контуры через SAM",
    "pl_sam_hint":        "Детектор заполнит классы polygon / mask / OBB прямоугольниками — "
                          "включите «Контуры через SAM», чтобы получить настоящие контуры.",
    "pl_sam_refine_tip":  "Только для моделей-детекторов: рамки, которые идут в классы polygon, mask или "
                          "OBB, обводятся SAM (модель из настроек ML) — настоящие контуры и плотные "
                          "повёрнутые рамки вместо прямоугольников. Медленнее: ещё один проход SAM на изображение.",
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
    "rm_text":            "Непроверенных аннотаций, сделанных моделью (🤖): на этом изображении — {cur}, во всех ваших изображениях — {all}.\n"
                          "Ручная и принятая (✓🤖) разметка не затрагивается.",
    "rm_current":         "Это изображение",
    "rm_all":             "Все изображения",
    "rm_done":            "Удалено аннотаций модели: {n}",
    "rm_none":            "Непроверенных аннотаций модели не найдено.",
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
