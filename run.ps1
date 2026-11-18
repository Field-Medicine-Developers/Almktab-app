# Almktab launcher for Windows PowerShell
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Find-Python {
    $venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) { return $venvPy }

    foreach ($cmd in @("py", "python", "python3")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) {
            if ($cmd -eq "py") { return "py" }
            return $found.Source
        }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Python غير مثبت أو غير موجود في PATH.`n`nثبّت Python 3.11+ من python.org وفعّل Add python.exe to PATH.`nثم عطّل App execution aliases للـ python من إعدادات ويندوز.",
        "Almktab",
        "OK",
        "Error"
    ) | Out-Null
    exit 1
}

$setup = Join-Path $PSScriptRoot "setup_gui.py"
if ($python -eq "py") {
    & py -3 $setup
} else {
    & $python $setup
}
