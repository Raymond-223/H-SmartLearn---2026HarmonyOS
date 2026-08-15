@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================================
echo H-SmartLearn Backend Launcher v1.7.3
echo Working directory: %CD%
echo ================================================================

if not exist "requirements.txt" (
  echo [ERROR] requirements.txt was not found in %CD%
  goto :failed
)

set "PY_CMD="
set "PY_VER="

where py.exe >nul 2>nul
if not errorlevel 1 (
  py -3.11 -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    set "PY_CMD=py"
    set "PY_VER=-3.11"
    goto :python_found
  )
  py -3.12 -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    set "PY_CMD=py"
    set "PY_VER=-3.12"
    goto :python_found
  )
  py -3.10 -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    set "PY_CMD=py"
    set "PY_VER=-3.10"
    goto :python_found
  )
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=python"
  set "PY_VER="
  goto :python_found
)

echo [ERROR] Python 3.10, 3.11, or 3.12 was not found.
echo Install Python from python.org and enable "Add Python to PATH".
goto :failed

:python_found
echo [1/5] Checking Python...
%PY_CMD% %PY_VER% -c "import sys; v=sys.version_info[:2]; assert v>=(3,10) and v<=(3,12), 'Python 3.10-3.12 required'; print(sys.version)"
if errorlevel 1 goto :failed

if not exist ".venv\Scripts\python.exe" (
  echo [2/5] Creating virtual environment...
  %PY_CMD% %PY_VER% -m venv ".venv"
  if errorlevel 1 goto :failed
) else (
  echo [2/5] Existing virtual environment found.
)

set "VENV_PY=%CD%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [ERROR] Virtual environment creation did not produce %VENV_PY%
  goto :failed
)

echo [3/5] Preparing pip...
"%VENV_PY%" -m pip install --disable-pip-version-check --upgrade pip setuptools wheel
if errorlevel 1 goto :failed

echo [4/5] Installing backend dependencies...
"%VENV_PY%" -m pip install --disable-pip-version-check -r "%CD%\requirements.txt"
if errorlevel 1 goto :failed

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  if errorlevel 1 goto :failed
)

echo [5/5] Starting FastAPI...
echo Host health check: http://127.0.0.1:8000/health
echo HarmonyOS emulator: http://10.0.2.2:8000
echo Keep this window open. Press Ctrl+C to stop.
echo ================================================================
"%VENV_PY%" "%CD%\start_backend.py"
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo [ERROR] Backend startup failed. Review the message above.
pause
exit /b 1
