import sqlite3

def migrate():
    try:
        conn = sqlite3.connect('creditos.db')
        cursor = conn.cursor()
        
        # Migración lugar_trabajo
        try:
            cursor.execute('ALTER TABLE clientes ADD COLUMN lugar_trabajo VARCHAR')
            print("Columna 'lugar_trabajo' agregada exitosamente.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                print(f"Error lugar_trabajo: {e}")

        # Migración foto_perfil
        try:
            cursor.execute('ALTER TABLE clientes ADD COLUMN foto_perfil VARCHAR')
            print("Columna 'foto_perfil' agregada exitosamente.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                print(f"Error foto_perfil: {e}")

        conn.commit()
    except Exception as e:
        print(f"Error inesperado: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate()
