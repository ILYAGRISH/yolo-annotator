@echo off
rem YOLO Annotator - start the app (creates .venv on the first run)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo First run: creating the Python environment ...
    call "%~dp0setup_venv.bat" --no-pause || (pause & exit /b 1)
)
rem .venv copied from another computer: it can't find its Python - make it again
".venv\Scripts\python.exe" -c "import sys" >nul 2>&1 || (
    echo The Python environment .venv was made on another computer - creating it again ...
    call "%~dp0setup_venv.bat" --no-pause || (pause & exit /b 1)
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
