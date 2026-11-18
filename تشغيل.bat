@echo off
chcp 65001 >nul
cd /d "%~dp0"
title برنامج المكتبة - التنصيب والتشغيل

where python >nul 2>nul
if errorlevel 1 (
  echo لم يتم العثور على Python.
  echo حمّل Python 3.11+ من https://www.python.org/downloads/
  echo وفعّل خيار: Add python.exe to PATH
  pause
  exit /b 1
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" setup_gui.py
) else (
  python setup_gui.py
)

if errorlevel 1 pause
