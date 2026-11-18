# Almktab silent launcher for Windows PowerShell
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$vbs = Join-Path $PSScriptRoot "run.vbs"
if (Test-Path $vbs) {
    Start-Process -FilePath "wscript.exe" -ArgumentList "`"$vbs`"" -WindowStyle Hidden
    exit 0
}

$setup = Join-Path $PSScriptRoot "setup_gui.py"
$venvPyw = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"
if (Test-Path $venvPyw) {
    Start-Process -FilePath $venvPyw -ArgumentList "`"$setup`"" -WindowStyle Hidden
    exit 0
}

$pythonw = Get-Command pythonw -ErrorAction SilentlyContinue
if ($pythonw) {
    Start-Process -FilePath $pythonw.Source -ArgumentList "`"$setup`"" -WindowStyle Hidden
    exit 0
}

Start-Process -FilePath (Join-Path $PSScriptRoot "run.bat")
