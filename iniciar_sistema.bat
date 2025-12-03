@echo off
echo Iniciando Creditos Jardin...
echo Por favor espere mientras se inicia el servidor.
echo No cierre esta ventana negra.

cd /d "%~dp0"
call venv\Scripts\activate

start http://localhost:8000

echo Servidor corriendo en http://localhost:8000
echo Para detenerlo, presione CTRL+C en esta ventana.

uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
pause
