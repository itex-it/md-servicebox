@echo off
setlocal
echo ==========================================
echo   ServiceBox API - Installation Script
echo ==========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.8+ is not found in your PATH.
    echo Please install Python from python.org and check "Add Python to PATH".
    pause
    exit /b 1
)

REM Create Virtual Environment if it doesn't exist
if not exist ".venv" (
    echo [INFO] Creating virtual environment (.venv)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [INFO] Virtual environment already exists.
)

REM Activate Virtual Environment
echo [INFO] Activating virtual environment...
call .venv\Scripts\activate

REM Install Python Dependencies
echo [INFO] Installing dependencies from requirements.txt...
pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

REM Install Playwright Browsers
echo [INFO] Installing Playwright Chromium browser...
playwright install chromium
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Playwright browser.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   [SUCCESS] Installation Complete!
echo ==========================================
echo.
echo You can now start the application using 'start_api.bat'.
echo.
pause
