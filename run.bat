@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY_VER=3.12.10"
set "PY_EXE=python-%PY_VER%-amd64.exe"
set "PY_URL=https://www.python.org/ftp/python/%PY_VER%/%PY_EXE%"
set "DL_DIR=%~dp0downloads"
set "INSTALLER=%DL_DIR%\%PY_EXE%"

REM If Python already available, launch GUI silently via VBS (no CMD left open)
call :FindPythonW
if defined PYW (
  start "" wscript.exe "%~dp0run.vbs"
  exit /b 0
)

call :FindPython
if defined PY (
  start "" wscript.exe "%~dp0run.vbs"
  exit /b 0
)

REM First-time: need console only for download/install
title Almktab - Installing Python
echo.
echo [INFO] Python not found. Downloading official installer...
echo.

if not exist "%DL_DIR%" mkdir "%DL_DIR%"

if not exist "%INSTALLER%" (
  echo Downloading:
  echo %PY_URL%
  echo.
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%INSTALLER%' -UseBasicParsing } catch { exit 1 }"
  if errorlevel 1 (
    echo [ERROR] Download failed.
    echo Open: https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
)

echo.
echo [INFO] Installing Python with PATH + Tcl/Tk...
"%INSTALLER%" /passive InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_tcltk=1 Include_test=0 AssociateFiles=1 SimpleInstall=1
if errorlevel 1 (
  echo [ERROR] Python install failed.
  pause
  exit /b 1
)

for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USERPATH=%%B"
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYSPATH=%%B"
set "PATH=%USERPATH%;%SYSPATH%;%PATH%"

echo.
echo [INFO] Launching setup window...
start "" wscript.exe "%~dp0run.vbs"
exit /b 0

:FindPythonW
set "PYW="
if exist "%~dp0.venv\Scripts\pythonw.exe" (
  set "PYW=%~dp0.venv\Scripts\pythonw.exe"
  goto :eof
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
  set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
  goto :eof
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" (
  set "PYW=%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
  goto :eof
)
where pythonw >nul 2>nul && set "PYW=pythonw"
goto :eof

:FindPython
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PY=%~dp0.venv\Scripts\python.exe"
  goto :eof
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  goto :eof
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
  set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
  goto :eof
)
where py >nul 2>nul && (
  set "PY=py -3"
  goto :eof
)
where python >nul 2>nul && (
  for /f "delims=" %%P in ('where python') do (
    echo %%P | find /I "WindowsApps" >nul
    if errorlevel 1 (
      set "PY=%%P"
      goto :eof
    )
  )
)
goto :eof
