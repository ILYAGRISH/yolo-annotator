# YOLO Annotator — Deploy

Ready-to-run copy of the current release. Everything needed to run the app on another Windows computer is in this folder.
Готовая к запуску копия текущей версии. В этой папке всё, что нужно для запуска на другом компьютере с Windows.

| File / Файл | Purpose / Назначение |
|---|---|
| `setup_venv.bat` | Creates `.venv` and installs dependencies / создаёт `.venv` и ставит зависимости |
| `run.bat` | Starts the app (runs setup automatically on the first start) / запускает программу (при первом запуске сам вызывает установку) |
| `About.md` | User guide (RU) / руководство пользователя |
| `requirements.txt` | Python packages / список пакетов |
| `main.py`, `annotator/`, `plugins/` | The application / сама программа |
| `setup_ml_env.bat`, `requirements-ml.txt`, `ml_backend/` | **Optional** ML environment (PyTorch, Ultralytics) / **необязательное** ML-окружение |

## Requirements / Требования

- Windows 10 / 11
- **Python 3.12+** (3.13 recommended / рекомендуется) — https://www.python.org/downloads/
  In the installer tick **"Add python.exe to PATH"** / в установщике отметьте **«Add python.exe to PATH»**.
- Internet on the first setup (~150 MB of packages) / интернет при первой установке (~150 МБ пакетов)

## Install / Установка

**1. Get the folder / Скачать папку**

- Whole repository as ZIP / весь репозиторий архивом:
  GitHub → **Code → Download ZIP** → unpack → open the `Deploy` folder / распаковать → открыть папку `Deploy`
- Only this folder with git / только эту папку через git:
  ```bat
  git clone --depth 1 --filter=blob:none --sparse https://github.com/ILYAGRISH/yolo-annotator.git
  cd yolo-annotator
  git sparse-checkout set Deploy
  cd Deploy
  ```

**2. Create the environment / Создать окружение** — double-click / двойной клик:

```
setup_venv.bat
```

It finds Python, creates `.venv` next to the app and installs PyQt6, Pillow, shapely, NumPy and OpenCV.
Скрипт находит Python, создаёт `.venv` рядом с программой и ставит PyQt6, Pillow, shapely, NumPy и OpenCV.

**3. Run / Запуск** — double-click / двойной клик:

```
run.bat
```

## Optional: ML environment / Необязательно: ML-окружение

Needed only for model features (YOLO pre-labelling, later SAM). The app works fully without it.
Нужно только для функций с моделями (предразметка YOLO, позже SAM). Без него программа полностью работает.

```
setup_ml_env.bat            (NVIDIA GPU is detected automatically / видеокарта определяется сама)
setup_ml_env.bat --cpu      (no NVIDIA GPU / без видеокарты NVIDIA)
```

Creates a separate `.venv-ml` with PyTorch and Ultralytics (up to ~3 GB). Then in the app: **ML → ML Settings… → Check**.
An existing Python / conda environment with `ultralytics` can be chosen there instead.
Создаёт отдельное окружение `.venv-ml` с PyTorch и Ultralytics (до ~3 ГБ). Затем в программе: **ML → Настройки ML… → Проверить**.
Вместо этого там можно выбрать уже готовый Python / conda-окружение с `ultralytics`.

## Update / Обновление

- ZIP: download the new version, replace everything **except** `.venv` (and `.venv-ml`), then run `setup_venv.bat` once more (updates packages if `requirements.txt` changed).
  Скачать новую версию, заменить всё **кроме** `.venv` (и `.venv-ml`), затем ещё раз запустить `setup_venv.bat` (обновит пакеты, если изменился `requirements.txt`).
- git: `git pull`, then / затем `setup_venv.bat`.

Projects (`*.annproj`) are stored wherever you create them, not inside `Deploy` — updating the app does not touch them.
Проекты (`*.annproj`) хранятся там, где вы их создали, а не внутри `Deploy`, — обновление программы их не затрагивает.

## Troubleshooting / Если что-то не так

| Problem / Проблема | Fix / Решение |
|---|---|
| `Python 3.12 or newer was not found` | Install Python 3.13 with "Add python.exe to PATH" / установить Python 3.13 с галкой «Add to PATH» |
| Setup failed half-way / установка прервалась | `setup_venv.bat --clean` — recreates `.venv` from scratch / пересоздаёт `.venv` с нуля |
| The app closes with an error / программа закрывается с ошибкой | The console window stays open — copy the error text / окно консоли остаётся открытым — скопируйте текст ошибки |

## License / Лицензия

GPL-3.0 — see / см. `LICENSE`.

## Documentation / Документация

- `About.md` — full user guide: annotation types, tools, semantic / panoptic mode, export formats, limitations (RU)
- Project page / страница проекта: https://github.com/ILYAGRISH/yolo-annotator
