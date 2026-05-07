@echo off
REM First-time setup for cartracker on Windows.
REM Creates a Python virtual environment in .venv and installs dependencies.
setlocal
cd /d "%~dp0"

REM Locate Python. The official installer registers the `py` launcher;
REM fall back to plain `python` if needed.
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYEXE=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYEXE=python"
    ) else (
        echo.
        echo Python is not installed or not on PATH.
        echo Download Python 3.11 or newer from https://www.python.org/downloads/
        echo During install, check "Add python.exe to PATH".
        echo.
        pause
        exit /b 1
    )
)

if not exist .venv (
    echo Creating virtual environment in .venv ...
    %PYEXE% -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Upgrading pip ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo Installing dependencies (this may take a couple minutes) ...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo Setup complete.
echo   - Put your saved listing .har / .html files in data\raw\
echo   - Double-click ingest.bat to load them into the database.
echo   - Double-click run.bat to launch the dashboard.
echo ============================================================
echo.
pause
exit /b 0

:fail
echo.
echo Setup failed. Scroll up to see the error.
pause
exit /b 1
