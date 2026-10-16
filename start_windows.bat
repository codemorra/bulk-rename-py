@echo off

REM Check if the project interpreter exists
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Error: Virtual environment not found. Please create it manually with:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    exit /b 1
)

REM Start the application
"%~dp0.venv\Scripts\python.exe" "%~dp0src\main.py" %*
