@echo off
echo Creando ejecutable...
.\venv\Scripts\pyinstaller --noconfirm --onefile --console --name "CreditosJardin" ^
    --add-data "app/templates;app/templates" ^
    --add-data "app/static;app/static" ^
    --hidden-import "uvicorn.logging" ^
    --hidden-import "uvicorn.loops" ^
    --hidden-import "uvicorn.loops.auto" ^
    --hidden-import "uvicorn.protocols" ^
    --hidden-import "uvicorn.protocols.http" ^
    --hidden-import "uvicorn.protocols.http.auto" ^
    --hidden-import "uvicorn.lifespan" ^
    --hidden-import "uvicorn.lifespan.on" ^
    --hidden-import "engineio.async_drivers.threading" ^
    run_app.py

echo.
echo Proceso finalizado. El ejecutable esta en la carpeta 'dist'.
pause