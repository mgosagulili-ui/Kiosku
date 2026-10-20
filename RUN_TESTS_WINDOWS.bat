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
".venv\Scripts\python.exe" main.py --check
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m unittest discover -v
if errorlevel 1 goto failed
echo.
echo Review the results above. A full run must have no failures, errors, or skipped tests.
echo Visual and hardware checks are listed in docs\ACCEPTANCE_CHECKLIST.md.
pause
exit /b 0
:failed
echo.
echo Verification did not pass. Read the error above.
pause
exit /b 1
