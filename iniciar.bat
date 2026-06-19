@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo               Iniciando Kyndo
echo ============================================
echo.

REM --- Verifica o ambiente do backend (venv) ---
if not exist "backend\venv\Scripts\python.exe" (
    echo [ERRO] venv do backend nao encontrado em backend\venv
    echo Crie com:
    echo     cd backend ^&^& python -m venv venv ^&^& venv\Scripts\activate ^&^& pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM --- Garante as dependencias do frontend ---
if not exist "frontend\node_modules" (
    echo [AVISO] node_modules nao encontrado. Instalando dependencias do frontend...
    pushd frontend
    call npm install
    popd
    echo.
)

echo Iniciando os servidores em segundo plano (sem janelas de terminal)...
echo.

REM --- Backend (python -m uvicorn) + Frontend (Vite/node) iniciados ocultos e desacoplados.
REM     Como rodam em segundo plano, voce pode fechar esta janela sem derrubar o app.
powershell -NoProfile -WindowStyle Hidden -Command ^
  "Start-Process -WindowStyle Hidden -WorkingDirectory '%~dp0backend' -FilePath '%~dp0backend\venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','main:app','--host','0.0.0.0','--port','8095';" ^
  "Start-Process -WindowStyle Hidden -WorkingDirectory '%~dp0frontend' -FilePath 'cmd.exe' -ArgumentList '/c','npm run dev'"

REM --- Aguarda subir e abre o navegador ---
timeout /t 6 /nobreak >nul
start "" http://localhost:5176

echo Kyndo iniciado em segundo plano:
echo.
echo    Backend  (API) : http://localhost:8095
echo    Frontend (Web) : http://localhost:5176
echo    Acesso na rede : http://10.1.1.61:5176
echo    Login padrao   : admin / admin
echo.
echo Pode FECHAR esta janela - os servidores continuam rodando.
echo Para encerrar de fato os servidores, use parar.bat.
echo.
timeout /t 8 /nobreak >nul
exit
