@echo off
REM Launch the Streamlit dashboard. Models retrain automatically on startup.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\streamlit.exe" (
    echo Streamlit not installed. Run setup.bat first.
    pause
    exit /b 1
)

if not exist "data\cars.db" (
    echo No database found. Running ingest first ...
    call "%~dp0ingest.bat"
    if errorlevel 1 exit /b 1
)

echo.
echo Launching Cartracker at http://localhost:8501
echo Press Ctrl+C in this window to stop.
echo.
".venv\Scripts\streamlit.exe" run app.py --server.port 8501 --browser.gatherUsageStats false
