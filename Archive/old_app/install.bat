@echo off
cd /d "%~dp0"
echo Creating virtual environment in .venv ...
py -3 -m venv .venv
echo Installing dependencies...
.venv\Scripts\pip install -r requirements.txt
echo.
echo Done! Run the app with run.bat
pause
