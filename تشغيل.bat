@echo off
cd /d "%~dp0"
start "" wscript.exe "%~dp0run.vbs"
exit /b 0
