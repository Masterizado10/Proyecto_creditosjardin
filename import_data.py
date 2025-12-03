import pandas as pd
from sqlalchemy import create_engine, text
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
    """Intenta parsear una fecha de varios formatos."""
    if pd.isna(date_val) or str(date_val).strip().lower() == 'nat':
        return None
    
    if isinstance(date_val, datetime.datetime):
        return date_val.date()
    
    date_str = str(date_val).strip()
    
    # Formatos comunes: DD.MM.YY, DD/MM/YYYY, YYYY-MM-DD
    formats = [
        "%d.%m.%y", "%d.%m.%Y", 
        "%d/%m/%y", "%d/%m/%Y", 
        "%Y-%m-%d"
    ]
    
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    return None

def clean_money(val):
    """Extrae un valor monetario de una cadena sucia."""
    if pd.isna(val):
        return 0.0
    
    s = str(val).strip()
    
    # Caso especial: Multiplicación explícita (ej: 110*19200)
    if '*' in s:
        parts = s.split('*')
        try:
            # Intentar multiplicar los dos números
            p1 = clean_money(parts[0])
            p2 = clean_money(parts[1])
            if p1 > 0 and p2 > 0:
                return p1 * p2
        except:
            pass

    if '$' in s:
        s = s.split('$')[1]
    
    s_clean = re.sub(r'[^\d.,]', '', s)
    
    if not s_clean:
        return 0.0
    
    try:
        # Asumir que . y , son separadores de miles si el número es grande
        s_final = s_clean.replace('.', '').replace(',', '')
        return float(s_final)
    except:
        return 0.0

def parse_plan_details(plan_str, monto_devolver_excel):
    """
    Interpreta la columna 'Plan. Pagos' respetando días hábiles.
    Retorna: (semanas_calculadas, monto_total_calculado, frecuencia_sugerida)
    
    Lógica de Conversión (Días Hábiles):
    - 1 Semana = 5 Días Hábiles
    - 1 Mes = 4 Semanas (20 Días Hábiles)
    - 1 Quincena = 2 Semanas (10 Días Hábiles)
    """
    s = str(plan_str).lower().strip()
    
    semanas = 0.0
    total = float(monto_devolver_excel) # Por defecto confiamos en la columna 'Monto Devolver'
    frecuencia = "Semanal"

    # Caso 1: Multiplicación explícita (ej: "110*19200") -> 110 Días * $19200 Diarios
    if '*' in s:
        parts = s.split('*')
        try:
            dias = float(parts[0].replace(',', '.'))
            diario = float(parts[1].replace(',', '.').replace('$','')) # Limpieza básica
            
            # Recalcular total si el Excel estaba vacío o mal
            if total == 0:
                total = dias * diario
            
            # Convertir Días a Semanas (Divisor 5)
            semanas = dias / 5
            frecuencia = "Semanal" # El sistema base es semanal
            return semanas, total, frecuencia
        except:
            pass

    # Extraer número del plan
    match = re.search(r'(\d+[\.,]?\d*)', s)
    if match:
        num = float(match.group(1).replace(',', '.'))
        
        if 'mes' in s:
            # 1 Mes = 4 Semanas
            semanas = num * 4
            frecuencia = "Mensual"
        elif 'quin' in s or 'q.' in s:
            # 1 Quincena = 2 Semanas
            semanas = num * 2
            frecuencia = "Quincenal"
        else:
            # Si es solo un número (ej: "110"), asumimos DÍAS si es alto (>20)
            if num > 20:
                semanas = num / 5 # Convertir días a semanas
            else:
                semanas = num # Asumir semanas si es bajo
            frecuencia = "Semanal"
    else:
        semanas = 1 # Fallback

    return semanas, total, frecuencia

def is_payment_column(col_name):
    return re.match(r'^\d{1,2}\.\d{1,2}\.\d{2,4}$', str(col_name)) is not None

def import_excel(file_path):
    if not os.path.exists(file_path):
        print(f"❌ Error: No se encontró el archivo '{file_path}'")
        return

    # --- LIMPIEZA DE BASE DE DATOS ---
    print("🧹 Limpiando base de datos antigua...")
    try:
        db.query(Pago).delete()
        db.query(Credito).delete()
        db.query(Cliente).delete()
        db.commit()
        print("✅ Base de datos vaciada correctamente.")
    except Exception as e:
        print(f"⚠️ Error limpiando BD: {e}")
        db.rollback()

    print(f"📂 Leyendo archivo: {file_path}...")
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"❌ Error al leer Excel: {e}")
        return

    df.columns = [str(c).strip() for c in df.columns]
    
    count_clientes = 0
    count_creditos = 0
    count_pagos = 0

    # Ordenar por CTO si existe para respetar el orden 1, 2, 3, 4
    if 'CTO.' in df.columns:
        try:
            df['CTO_Clean'] = pd.to_numeric(df['CTO.'], errors='coerce').fillna(0)
            df = df.sort_values(by=['Nombre y Apellido', 'CTO_Clean'])
        except:
            pass

    for index, row in df.iterrows():
        try:
            # 1. Cliente
            nombre = str(row.get('Nombre y Apellido', '')).strip()
            dni = str(row.get('D.N.I', '')).strip()
            domicilio = str(row.get('Domicilio part. y laboral', '')).strip()
            
            if not nombre or nombre.lower() == 'nan':
                continue
            
            if not dni or dni.lower() == 'nan':
                dni = f"S/D-{index}" # Generar DNI temporal si falta

            # Buscar o Crear Cliente
            cliente = db.query(Cliente).filter(Cliente.dni == dni).first()
            if not cliente:
                cliente = db.query(Cliente).filter(Cliente.nombre == nombre).first()
                
            if not cliente:
                cliente = Cliente(
                    nombre=nombre,
                    dni=dni,
                    direccion=domicilio,
                    telefono="Sin registrar",
                    fecha_registro=datetime.date.today()
                )
                db.add(cliente)
                db.commit()
                db.refresh(cliente)
                count_clientes += 1
            
            # 2. Crédito
            try:
                monto_prestado = clean_money(row.get('Capital', 0))
                monto_devolver_excel = clean_money(row.get('Monto Devolver', 0))
                
                # Calcular Semanas y Total usando lógica de Días Hábiles
                plan_str = str(row.get('Plan. Pagos', ''))
                semanas, monto_total, frecuencia = parse_plan_details(plan_str, monto_devolver_excel)
                
                # Si el total calculado es 0, usar el prestado
                if monto_total == 0:
                    monto_total = monto_prestado

                # Calcular Cuota Semanal Equivalente
                # El sistema necesita saber cuánto se paga por periodo.
                # Si la frecuencia es Semanal, la cuota es Total / Semanas
                if semanas > 0:
                    pago_semanal = monto_total / semanas
                else:
                    pago_semanal = 0

                fecha_inicio = parse_date(row.get('Fecha Inicio del credito'))
                if not fecha_inicio:
                    fecha_inicio = datetime.date.today()

                cto_num = str(row.get('CTO.', ''))

                credito = Credito(
                    cliente_id=cliente.id,
                    monto_prestado=monto_prestado,
                    tasa_interes=0, 
                    monto_total=monto_total,
                    semanas=semanas,
                    frecuencia=frecuencia,
                    pago_semanal=pago_semanal,
                    fecha_inicio=fecha_inicio,
                    activo=True
                )
                db.add(credito)
                db.commit()
                db.refresh(credito)
                count_creditos += 1

                # 3. Pagos
                payment_cols = [c for c in df.columns if is_payment_column(c)]
                
                for col_fecha in payment_cols:
                    raw_val = row.get(col_fecha)
                    monto_pago = clean_money(raw_val)
                    
                    if monto_pago > 0:
                        fecha_pago = parse_date(col_fecha)
                        if fecha_pago:
                            pago = Pago(
                                credito_id=credito.id,
                                monto=monto_pago,
                                fecha=fecha_pago,
                                nota=f"Imp. Excel (CTO {cto_num})"
                            )
                            db.add(pago)
                            count_pagos += 1
                
                db.commit()

            except Exception as e:
                print(f"⚠️ Error procesando crédito para {nombre}: {e}")
                db.rollback()
                continue

        except Exception as e:
            print(f"❌ Error general en fila {index+2}: {e}")
            db.rollback()

    print("\n✅ Importación Finalizada (Lógica Días Hábiles Aplicada)")
    print(f"👥 Clientes: {count_clientes}")
    print(f"💰 Créditos: {count_creditos}")
    print(f"💵 Pagos: {count_pagos}")

if __name__ == "__main__":
    EXCEL_FILE = "datos_clientes.xlsx" 
    print("="*50)
    print("🚀 INICIANDO MIGRACIÓN DE DATOS v2")
    print("   - Lógica: 1 Semana = 5 Días Hábiles")
    print("   - Limpieza automática de BD previa")
    print("="*50)
    
    if not os.path.exists(EXCEL_FILE):
        print(f"⚠️  No se encontró '{EXCEL_FILE}'")
    else:
        import_excel(EXCEL_FILE)
