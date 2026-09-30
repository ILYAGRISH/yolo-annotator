@echo off
rem YOLO Annotator - start the app (creates .venv on the first run)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo First run: creating the Python environment ...
    call setup_venv.bat --no-pause || (pause & exit /b 1)
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
