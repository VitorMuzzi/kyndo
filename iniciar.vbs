Dim fso, base
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)

Dim wmi, startup, proc
Set wmi = GetObject("winmgmts:\\.\root\cimv2")
Set startup = wmi.Get("Win32_ProcessStartup").SpawnInstance_
startup.ShowWindow = 0

Set proc = wmi.Get("Win32_Process")

Dim pidBack, pidFront
proc.Create "cmd /c """ & base & "\backend\venv\Scripts\uvicorn.exe"" main:app --port 8000", base & "\backend", startup, pidBack
WScript.Sleep 4000
proc.Create "cmd /c """ & base & "\frontend\node_modules\.bin\vite"" --port 5176", base & "\frontend", startup, pidFront
WScript.Sleep 5000

WScript.CreateObject("WScript.Shell").Run "http://localhost:5176"
MsgBox "Kyndo iniciado!" & Chr(10) & "Backend: http://localhost:8000" & Chr(10) & "Frontend: http://localhost:5176" & Chr(10) & Chr(10) & "Para encerrar, use parar.bat", 64, "Kyndo"
