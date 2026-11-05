@echo off
REM run.bat — Clean start script for Sahayak AI on Windows

echo =============================================
echo    Starting Sahayak AI Support Assistant
echo =============================================

cd /d "%~dp0"

REM 1. Clean temporary files and caches
echo Cleaning Python cache and temporary files...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul

REM 2. Activate virtual environment if present
if exist ".venv\Scripts\activate.bat" (
    echo Activating .venv virtual environment...
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    echo Activating venv virtual environment...
    call venv\Scripts\activate.bat
)

REM 3. Launch Streamlit
echo Starting Streamlit on port 8501...
streamlit run app.py --server.headless=true --server.port=8501
pause

