@echo off
rem ===========================================================================
rem  YOLO Annotator - create / update the Python virtual environment (.venv)
rem
rem  Usage:  setup_venv.bat              create .venv (or update packages)
rem          setup_venv.bat --clean      delete .venv and create it again
rem          setup_venv.bat --no-pause   do not wait for a key at the end
rem ===========================================================================
setlocal
cd /d "%~dp0"
title YOLO Annotator - setup

set "CLEAN="
set "NOPAUSE="
for %%A in (%*) do (
    if /i "%%~A"=="--clean"    set "CLEAN=1"
    if /i "%%~A"=="--no-pause" set "NOPAUSE=1"
)

rem --- 1. Find Python 3.12+ (3.13 preferred; numpy 2.5 needs 3.12) ----------
set "PY="
for %%V in (3.13 3.12) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
    )
)
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python 3.12 or newer was not found.
    echo         Install Python 3.13 from https://www.python.org/downloads/
    echo         and tick "Add python.exe to PATH" in the installer.
    goto :fail
)
echo Using Python:
%PY% --version

rem --- 2. Create .venv --------------------------------------------------------
if defined CLEAN if exist ".venv" (
    echo Removing old .venv ...
    rmdir /s /q ".venv"
)
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv ...
    %PY% -m venv .venv || goto :fail
)

rem --- 3. Install dependencies ------------------------------------------------
echo Installing dependencies (first run downloads ~150 MB) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail

rem --- 4. Check -------------------------------------------------------------
".venv\Scripts\python.exe" -c "import PyQt6.QtWidgets, PIL, shapely, numpy, cv2; print('Dependencies OK')" || goto :fail

echo.
echo Done! Start the app with run.bat
if not defined NOPAUSE pause
exit /b 0

:fail
echo.
echo [ERROR] Setup failed - see the messages above.
echo         To start from scratch run:  setup_venv.bat --clean
if not defined NOPAUSE pause
exit /b 1
