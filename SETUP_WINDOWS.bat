@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>&1
if errorlevel 1 (
    where python >nul 2>&1
    if errorlevel 1 goto no_python
    python -m venv .venv
) else (
    py -3 -m venv .venv
)
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" main.py --check
if errorlevel 1 goto failed
echo.
echo Setup finished. Run RUN_WINDOWS.bat to open Kiosku.
echo Run RUN_TESTS_WINDOWS.bat before using it for real orders.
pause
exit /b 0
:no_python
echo Python was not found. Install Python 3.13 and enable its PATH option.
pause
exit /b 1
:failed
echo.
echo Setup did not finish. Read the error above; internet access is needed to install packages.
pause
exit /b 1
