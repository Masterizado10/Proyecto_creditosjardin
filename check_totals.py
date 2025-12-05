import pandas as pd
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models import Base, Cliente, Credito, Pago
from app.database import SQLALCHEMY_DATABASE_URL as DATABASE_URL

# Re-use the clean_money function exactly as it is in import_data.py
def clean_money(val):
    """Extrae un valor monetario de una cadena sucia, evitando concatenar números de texto."""
    if pd.isna(val):
        return 0.0
    
    if isinstance(val, (int, float)):
        return float(val)
    
    s = str(val).strip()
    
    if '*' in s:
        parts = s.split('*')
        try:
            p1 = clean_money(parts[0])
            p2 = clean_money(parts[1])
            if p1 > 0 and p2 > 0:
                return p1 * p2
        except:
            pass

    if '$' in s:
        s = s.split('$')[1]
    
    try:
        clean_s = s.replace('$', '').replace(' ', '')
        return float(clean_s)
    except:
        pass

    matches = re.findall(r'[\d]+[.,\d]*', s)
    
    if not matches:
        return 0.0
    
    candidates = []
    for m in matches:
        try:
            clean_m = m
            if '.' in m and ',' in m:
                if m.rfind('.') > m.rfind(','): 
                    clean_m = m.replace(',', '')
                else: 
                    clean_m = m.replace('.', '').replace(',', '.')
            elif '.' in m:
                parts = m.split('.')
                if len(parts) > 1 and len(parts[-1]) == 3:
                    clean_m = m.replace('.', '')
                else:
                    clean_m = m 
            elif ',' in m:
                parts = m.split(',')
                if len(parts) > 1 and len(parts[-1]) == 3:
                    clean_m = m.replace(',', '')
                else:
                    clean_m = m.replace(',', '.')
            
            val_float = float(clean_m)
            candidates.append(val_float)
        except:
            continue
            
    if not candidates:
        return 0.0
        
    return max(candidates)

def check_totals():
    file_path = "datos_clientes.xlsx"
    print(f"📂 Analizando Excel: {file_path}")
    
    try:
        df = pd.read_excel(file_path)
        
        # Identify columns
        col_pendiente = "Pendiente $$$"
        col_acumulado = "Acumulado $$$"
        col_devolver = "Monto Devolver"
        
        total_pendiente_excel = 0
        total_acumulado_excel = 0
        total_devolver_excel = 0
        
        print("\n--- Sumando Excel (Fila por Fila) ---")
        for index, row in df.iterrows():
            # Apply same filter as import_data.py
            if pd.isna(row.get(col_pendiente)):
                continue
                
            p = clean_money(row.get(col_pendiente, 0))
            a = clean_money(row.get(col_acumulado, 0))
            d = clean_money(row.get(col_devolver, 0))
            
            total_pendiente_excel += p
            total_acumulado_excel += a
            total_devolver_excel += d
            
            # Debug high values to see if any single row is skewing the result
            if p > 5000000: # > 5 million
                print(f"⚠️ Fila {index} ({row.get('Nombre y Apellido')}) tiene Pendiente ALTO: {p:,.2f}")

        print(f"\n📊 TOTALES EXCEL (Calculados con clean_money):")
        print(f"   Pendiente: ${total_pendiente_excel:,.2f}")
        print(f"   Acumulado (Pagado): ${total_acumulado_excel:,.2f}")
        print(f"   Monto Devolver (Total): ${total_devolver_excel:,.2f}")
        
        # Check DB
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        print("\n--- Totales Base de Datos ---")
        creditos = db.query(Credito).all()
        
        db_total_prestado = 0
        db_total_deuda = 0
        db_total_pagado = 0
        db_saldo_restante = 0
        
        for c in creditos:
            pagado = sum([p.monto for p in c.pagos])
            restante = c.monto_total - pagado
            
            db_total_deuda += c.monto_total
            db_total_pagado += pagado
            db_saldo_restante += restante
            
            if restante > 5000000:
                 print(f"⚠️ DB Crédito {c.id} (Cliente {c.cliente_id}) Restante ALTO: {restante:,.2f}")

        print(f"📊 TOTALES DB:")
        print(f"   Total Deuda (Monto Total): ${db_total_deuda:,.2f}")
        print(f"   Total Pagado: ${db_total_pagado:,.2f}")
        print(f"   Saldo Restante (Por Cobrar): ${db_saldo_restante:,.2f}")
        
        diff = db_saldo_restante - total_pendiente_excel
        print(f"\n📉 DIFERENCIA (DB - Excel): ${diff:,.2f}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_totals()
