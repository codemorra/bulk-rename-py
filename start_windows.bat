@echo off

REM Check if .venv exists
if not exist ".venv" (
    echo Error: Virtual environment not found. Please create it manually with:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    exit /b 1
)

REM Activate virtual environment
call .venv\Scripts\activate

REM Start the application
python src\main.py