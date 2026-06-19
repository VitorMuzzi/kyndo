@echo off
setlocal
echo Parando Kyndo...

set "found="

REM Encerra quem estiver escutando na porta do backend (8095)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8095" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    set "found=1"
)

REM Encerra quem estiver escutando na porta do frontend (5176)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5176" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    set "found=1"
)

if defined found (
    echo Kyndo parado.
) else (
    echo Nenhum servidor do Kyndo estava rodando nas portas 8095/5176.
)

timeout /t 3 /nobreak >nul
