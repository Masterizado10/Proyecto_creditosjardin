from sqlalchemy import create_engine, text
from app.database import SQLALCHEMY_DATABASE_URL

def migrate():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE creditos ADD COLUMN frecuencia VARCHAR DEFAULT 'Semanal'"))
            print("Columna 'frecuencia' agregada exitosamente.")
        except Exception as e:
            print(f"Error (puede que ya exista): {e}")

if __name__ == "__main__":
    migrate()
