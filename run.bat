@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Almktab Setup

REM Prefer Windows Python launcher, then python, then py -3
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY where python3 >nul 2>nul && set "PY=python3"

if not defined PY (
  echo.
  echo [ERROR] Python was not found.
  echo.
  echo Install Python 3.11+ from:
  echo   https://www.python.org/downloads/
  echo.
  echo During setup, ENABLE:
  echo   - Add python.exe to PATH
  echo.
  echo Also disable Store aliases:
  echo   Settings ^> Apps ^> Advanced app settings ^> App execution aliases
  echo   Turn OFF "python.exe" and "python3.exe"
  echo.
  pause
  exit /b 1
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" setup_gui.py
) else (
  %PY% setup_gui.py
)

if errorlevel 1 (
  echo.
  echo [ERROR] Setup window failed to start.
  pause
  exit /b 1
)

endlocal
