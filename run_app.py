import uvicorn
import os
import sys
import webbrowser
from threading import Timer

def open_browser():
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    # Si se ejecuta como ejecutable compilado por PyInstaller
    if getattr(sys, 'frozen', False):
        # El directorio base es donde se extrae el ejecutable temporalmente
        base_dir = sys._MEIPASS
    else:
        # El directorio base es el directorio actual
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # Cambiar el directorio de trabajo al directorio base para que FastAPI encuentre 'app'
    # Sin embargo, si 'app' está empaquetado, necesitamos asegurarnos de que uvicorn lo encuentre.
    # Una mejor estrategia con PyInstaller y uvicorn es importar la app directamente.
    
    # Agregar el directorio actual al path para poder importar app
    sys.path.insert(0, base_dir)

    # Programar la apertura del navegador
    Timer(1.5, open_browser).start()

    # Ejecutar Uvicorn
    # Usamos "app.main:app" si estamos en desarrollo, pero importando el objeto app directamente es mejor para congelar
    try:
        from app.main import app
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except ImportError as e:
        print(f"Error importando la aplicación: {e}")
        input("Presione Enter para salir...")
