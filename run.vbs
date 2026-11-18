' Silent launcher — no CMD window
Option Explicit
Dim sh, fso, root, venvPyw, venvPy, setup, cmd, rc
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = root
setup = root & "\setup_gui.py"

venvPyw = root & "\.venv\Scripts\pythonw.exe"
venvPy = root & "\.venv\Scripts\python.exe"

If fso.FileExists(venvPyw) Then
  cmd = """" & venvPyw & """ """ & setup & """"
  sh.Run cmd, 0, False
  WScript.Quit 0
End If

If fso.FileExists(venvPy) Then
  cmd = """" & venvPy & """ """ & setup & """"
  sh.Run cmd, 0, False
  WScript.Quit 0
End If

' Prefer system pythonw
Dim candidates, i, p
candidates = Array( _
  sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"), _
  sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"), _
  sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"), _
  "pythonw.exe" _
)

For i = 0 To UBound(candidates)
  p = candidates(i)
  On Error Resume Next
  rc = sh.Run("""" & p & """ """ & setup & """", 0, False)
  If Err.Number = 0 Then
    WScript.Quit 0
  End If
  Err.Clear
  On Error GoTo 0
Next

' Fallback: run.bat (may show console only if Python must be installed)
sh.Run """" & root & "\run.bat""", 1, False
