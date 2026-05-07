@echo off
REM Wipe the database and re-ingest every file in data\raw\.
REM Run this after dropping new saved-listing .har / .html / .json files into data\raw\.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

if not exist "data\raw" (
    echo data\raw does not exist. Create it and drop your saved listing files in.
    pause
    exit /b 1
)

dir /b "data\raw\*.har" "data\raw\*.html" "data\raw\*.htm" "data\raw\*.json" >nul 2>nul
if errorlevel 1 (
    echo No .har / .html / .json files found in data\raw\.
    echo Save a vehicle-listing search there before running ingest.
    pause
    exit /b 1
)

if exist "data\cars.db" del /f /q "data\cars.db"
".venv\Scripts\python.exe" ingest.py html data\raw
if errorlevel 1 (
    echo Ingest failed.
    pause
    exit /b 1
)

echo.
echo Ingest complete. Run run.bat to view the dashboard.
pause
