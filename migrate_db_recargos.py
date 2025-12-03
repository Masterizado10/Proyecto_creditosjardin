import sqlite3

def migrate():
    conn = sqlite3.connect('creditos.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE creditos ADD COLUMN recargos FLOAT DEFAULT 0.0")
        print("Columna 'recargos' agregada a la tabla 'creditos'.")
    except sqlite3.OperationalError as e:
        print(f"Error al agregar columna (probablemente ya existe): {e}")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
