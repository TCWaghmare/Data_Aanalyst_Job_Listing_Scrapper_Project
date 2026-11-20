' Starts Fresher Job Finder and Background Automated Scheduler silently without a command prompt window
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir

' Launch server silently (0 = hidden)
WshShell.Run "python start.py", 0, False

' Give server a moment to start, then open the web dashboard
WScript.Sleep 1500
WshShell.Run "http://127.0.0.1:8000"
