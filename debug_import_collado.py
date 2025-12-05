import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Cliente, Credito, Pago
from app.database import SQLALCHEMY_DATABASE_URL as DATABASE_URL
import datetime
import re
import os

# Configuración de la Base de Datos
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

def parse_date(date_val):
    if pd.isna(date_val) or str(date_val).strip().lower() == 'nat':
        return None
    if isinstance(date_val, datetime.datetime):
        return date_val.date()
    date_str = str(date_val).strip()
    formats = ["%d.%m.%y", "%d.%m.%Y", "%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

def clean_money(val):
    if pd.isna(val): return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).strip()
    if '*' in s:
        parts = s.split('*')
        try:
            p1 = clean_money(parts[0])
            p2 = clean_money(parts[1])
            if p1 > 0 and p2 > 0: return p1 * p2
        except: pass
    if '$' in s: s = s.split('$')[1]
    try:
        clean_s = s.replace('$', '').replace(' ', '')
        return float(clean_s)
    except: pass
    matches = re.findall(r'[\d]+[.,\d]*', s)
    if not matches: return 0.0
    for m in matches:
        try:
            clean_m = m
            if '.' in m and ',' in m:
                if m.rfind('.') > m.rfind(','): clean_m = m.replace(',', '')
                else: clean_m = m.replace('.', '').replace(',', '.')
            elif '.' in m:
                parts = m.split('.')
                if len(parts) > 1 and len(parts[-1]) == 3: clean_m = m.replace('.', '')
                else: clean_m = m
            return float(clean_m)
        except: continue
    return 0.0

def parse_plan_details(plan_str, monto_devolver_excel):
    s = str(plan_str).lower().strip()
    semanas = 0.0
    total = float(monto_devolver_excel)
    frecuencia = "Semanal"
    if '*' in s:
        parts = s.split('*')
        try:
            dias = clean_money(parts[0])
            diario = clean_money(parts[1])
            total_calculado = dias * diario
            if total_calculado > 0: total = total_calculado
            semanas = dias / 5
            frecuencia = "Semanal"
            return semanas, total, frecuencia
        except: pass
    match = re.search(r'(\d+[\.,]?\d*)', s)
    if match:
        num = float(match.group(1).replace(',', '.'))
        if 'mes' in s:
            semanas = num * 4
            frecuencia = "Mensual"
        elif 'quin' in s or 'q.' in s:
            semanas = num * 2
            frecuencia = "Quincenal"
        else:
            if num > 20: semanas = num / 5
            else: semanas = num
            frecuencia = "Semanal"
    else:
        semanas = 1
    return semanas, total, frecuencia

def debug_import():
    file_path = "datos_clientes.xlsx"
    print(f"Leyendo archivo: {file_path}...")
    df = pd.read_excel(file_path)
    df.columns = [str(c).strip() for c in df.columns]
    
    mask = df.apply(lambda row: row.astype(str).str.contains('Collado', case=False).any(), axis=1)
    collado_rows = df[mask]
    
    print(f"Found {len(collado_rows)} rows for Collado.")
    
    for index, row in collado_rows.iterrows():
        print(f"\n--- Processing Row {index+2} ---")
        nombre = str(row.get('Nombre y Apellido', '')).strip()
        dni = str(row.get('D.N.I', '')).strip()
        pendiente_check = row.get('Pendiente $$$')
        
        print(f"Nombre: {nombre}")
        print(f"DNI: {dni}")
        print(f"Pendiente $$$: {pendiente_check} (Type: {type(pendiente_check)})")
        
        if pd.isna(pendiente_check):
            print("Saltando fila - Columna 'Pendiente $$$' vacia.")
            continue
            
        if not nombre or nombre.lower() == 'nan':
            print("Saltando fila - Nombre vacio.")
            continue
            
        print("Row passed basic validation.")
        
        # Check Plan Parsing
        monto_devolver_excel = clean_money(row.get('Monto Devolver', 0))
        plan_str = str(row.get('Plan. Pagos', ''))
        print(f"Plan String: {plan_str}")
        print(f"Monto Devolver Excel: {monto_devolver_excel}")
        
        semanas, monto_total, frecuencia = parse_plan_details(plan_str, monto_devolver_excel)
        print(f"Parsed: Semanas={semanas}, Total={monto_total}, Frecuencia={frecuencia}")

if __name__ == "__main__":
    debug_import()
