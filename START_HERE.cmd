@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title B-roll Workflow

echo ========================================
echo B-roll Workflow
echo ========================================
echo.

py -3.11 --version >nul 2>nul
if not errorlevel 1 (
  set "PY=py -3.11"
  goto :python_ready
)
python --version >nul 2>nul
if not errorlevel 1 (
  python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)" >nul 2>nul
  if not errorlevel 1 (
    set "PY=python"
    goto :python_ready
  )
)

echo Python 3.11 not found. Trying automatic install...
where winget >nul 2>nul
if errorlevel 1 goto :no_python
winget install -e --id Python.Python.3.11 --scope user --silent --accept-package-agreements --accept-source-agreements
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
  set "PY=%LocalAppData%\Programs\Python\Python311\python.exe"
  goto :python_ready
)
goto :no_python

:python_ready
if not exist .venv\Scripts\python.exe (
  echo [1/3] Preparing local runtime...
  %PY% -m venv .venv
  if errorlevel 1 goto :failed
)

echo [2/3] Checking components...
.venv\Scripts\python.exe -c "import fastapi,uvicorn,httpx,edge_tts,imageio_ffmpeg,mutagen,pyJianYingDraft" >nul 2>nul
if errorlevel 1 (
  echo Installing required components...
  .venv\Scripts\python.exe -m pip install -U pip
  if errorlevel 1 goto :failed
  .venv\Scripts\python.exe -m pip install -r apps\server\requirements.txt
  if errorlevel 1 goto :failed
)

echo [3/3] Starting B-roll Workflow...
.venv\Scripts\python.exe run_local.py
exit /b %errorlevel%

:no_python
echo.
echo ERROR: Python 3.11 could not be installed automatically.
echo Install Python 3.11 once, then run START_HERE.cmd again.
goto :hold

:failed
echo.
echo ERROR: Setup failed.
goto :hold

:hold
pause
exit /b 1
