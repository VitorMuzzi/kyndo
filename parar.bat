@echo off
echo Parando Kyndo...
taskkill /F /IM uvicorn.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1
echo Kyndo parado.
