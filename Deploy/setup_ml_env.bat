@echo off
rem ===========================================================================
rem  YOLO Annotator - create / update the ML environment (.venv-ml)
rem
rem  The ML backend (YOLO, later SAM) runs in its OWN Python environment, so
rem  PyTorch (~3 GB) never touches the main app environment (.venv).
rem
rem  Usage:  setup_ml_env.bat              create .venv-ml (or update packages)
rem          setup_ml_env.bat --cpu        force the CPU build of PyTorch
rem          setup_ml_env.bat --clean      delete .venv-ml and create it again
rem          setup_ml_env.bat --no-pause   do not wait for a key at the end
rem ===========================================================================
setlocal
cd /d "%~dp0"
title YOLO Annotator - ML setup

set "CLEAN="
set "NOPAUSE="
set "FORCECPU="
for %%A in (%*) do (
    if /i "%%~A"=="--clean"    set "CLEAN=1"
    if /i "%%~A"=="--no-pause" set "NOPAUSE=1"
    if /i "%%~A"=="--cpu"      set "FORCECPU=1"
)

rem --- 1. Find Python 3.10+ (3.13 preferred) ---------------------------------
set "PY="
for %%V in (3.13 3.12 3.11 3.10) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
    )
)
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python 3.10 or newer was not found.
    echo         Install Python 3.13 from https://www.python.org/downloads/
    echo         and tick "Add python.exe to PATH" in the installer.
    goto :fail
)
echo Using Python:
%PY% --version

rem --- 2. GPU or CPU build of PyTorch -----------------------------------------
rem  CUDA 12.8 wheels support every current NVIDIA GPU, including RTX 50xx
rem  (Blackwell); they need an NVIDIA driver 570 or newer.
set "TORCH_INDEX=https://download.pytorch.org/whl/cpu"
set "DEVICE=CPU"
if not defined FORCECPU (
    nvidia-smi >nul 2>&1 && (
        set "TORCH_INDEX=https://download.pytorch.org/whl/cu128"
        set "DEVICE=NVIDIA GPU (CUDA 12.8)"
    )
)
echo PyTorch build: %DEVICE%

rem --- 3. Create .venv-ml -----------------------------------------------------
if defined CLEAN if exist ".venv-ml" (
    echo Removing old .venv-ml ...
    rmdir /s /q ".venv-ml"
)
if not exist ".venv-ml\Scripts\python.exe" (
    echo Creating ML environment in .venv-ml ...
    %PY% -m venv .venv-ml || goto :fail
)

rem --- 4. Install -------------------------------------------------------------
echo Installing PyTorch (first run downloads up to ~3 GB, be patient) ...
".venv-ml\Scripts\python.exe" -m pip install --upgrade pip || goto :fail
rem  Verified pair (RTX 5060 Ti, CUDA 12.8): torch 2.11.0 + torchvision 0.26.0
".venv-ml\Scripts\python.exe" -m pip install torch==2.11.0 torchvision==0.26.0 --index-url %TORCH_INDEX% || goto :fail
echo Installing ML packages ...
".venv-ml\Scripts\python.exe" -m pip install -r requirements-ml.txt || goto :fail

rem --- 5. Check -------------------------------------------------------------
".venv-ml\Scripts\python.exe" -c "import torch, ultralytics; print('torch', torch.__version__, '| CUDA:', torch.cuda.is_available(), '| ultralytics', ultralytics.__version__)" || goto :fail

echo.
echo Done! In the app open  ML ^> ML Settings...  and press "Check".
if not defined NOPAUSE pause
exit /b 0

:fail
echo.
echo [ERROR] ML setup failed - see the messages above.
echo         To start from scratch run:  setup_ml_env.bat --clean
echo         Without an NVIDIA GPU run:   setup_ml_env.bat --cpu
if not defined NOPAUSE pause
exit /b 1
