@echo off
echo [INFO] Starting ServiceBox API...
echo.

if not exist ".venv" (
    echo [ERROR] Virtual environment not found. Please run 'install.bat' first.
    pause
    exit /b 1
)

call .venv\Scripts\activate
:loop
python servicebox_api.py
if %ERRORLEVEL% EQU 10 (
    echo [INFO] Restarting ServiceBox API...
    timeout /t 2
    goto loop
)
echo [INFO] ServiceBox API stopped.
pause
