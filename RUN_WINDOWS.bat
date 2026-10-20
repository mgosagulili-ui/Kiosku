@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
if not exist ".venv\Scripts\python.exe" (
    echo Run SETUP_WINDOWS.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" pause
exit /b %RESULT%
