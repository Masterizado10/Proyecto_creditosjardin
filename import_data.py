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
    """Extrae un valor monetario de una cadena sucia, evitando concatenar números de texto."""
    if pd.isna(val):
        return 0.0
    
    # Si ya es número, devolverlo directamente
    if isinstance(val, (int, float)):
        return float(val)
    
    s = str(val).strip()
    
    # Caso especial: Multiplicación explícita (ej: 110*19200)
    if '*' in s:
        parts = s.split('*')
        try:
            # Limpiar cada parte individualmente
            p1 = clean_money(parts[0])
            p2 = clean_money(parts[1])
            if p1 > 0 and p2 > 0:
                return p1 * p2
        except:
            pass

    # Si hay signo $, tomar lo que sigue
    if '$' in s:
        s = s.split('$')[1]
    
    # Intentar conversión directa primero (maneja "540000.0" correctamente)
    try:
        # Eliminar espacios y símbolos de moneda comunes antes de intentar
        clean_s = s.replace('$', '').replace(' ', '')
        return float(clean_s)
    except:
        pass

    # Estrategia: Buscar todas las secuencias numéricas posibles
    matches = re.findall(r'[\d]+[.,\d]*', s)
    
    if not matches:
        return 0.0
    
    candidates = []
    for m in matches:
        try:
            # Heurística para detectar separadores
            # Si tiene punto y coma, el último es el decimal
            clean_m = m
            if '.' in m and ',' in m:
                if m.rfind('.') > m.rfind(','): # Estilo US: 1,000.00
                    clean_m = m.replace(',', '')
                else: # Estilo AR/EU: 1.000,00
                    clean_m = m.replace('.', '').replace(',', '.')
            elif '.' in m:
                # Solo puntos. 
                # Si el punto está seguido de 3 dígitos exactos, asumimos miles (ej: 100.000)
                # Si no, asumimos decimal (ej: 540000.0 o 10.5)
                parts = m.split('.')
                if len(parts) > 1 and len(parts[-1]) == 3:
                    clean_m = m.replace('.', '')
                else:
                    clean_m = m # Dejar el punto como decimal
            elif ',' in m:
                # Solo comas.
                # Si la coma está seguida de 3 dígitos, asumimos miles (ej: 100,000)
                # Si no, asumimos decimal (ej: 10,5)
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

def extract_phone(domicilio_str):
    """Intenta extraer un número de teléfono del campo domicilio."""
    if pd.isna(domicilio_str):
        return "Sin registrar"
    
    s = str(domicilio_str)
    
    # Buscar patrones comunes de teléfono (Cel, Tel, o secuencias largas de números)
    # Regex para capturar números de 7 a 15 dígitos, permitiendo espacios o guiones
    # Ignoramos números cortos que podrían ser altura de calle
    
    # 1. Buscar explícitamente etiquetas
    phone_match = re.search(r'(?:cel|tel|wsp|movil|fijo)[:\.\s-]*([\d\s-]{6,})', s, re.IGNORECASE)
    if phone_match:
        return phone_match.group(1).strip()
    
    # 2. Si no hay etiqueta, buscar secuencia de números larga (ej: 351-1234567)
    # Excluir si parece ser una dirección (ej: "San Martin 1234")
    # Buscamos algo que tenga al menos 8 dígitos
    digits_match = re.findall(r'\b\d[\d\s-]{7,}\d\b', s)
    if digits_match:
        # Retornar el último encontrado (a veces la dirección tiene números largos, pero el tel suele ir al final)
        return digits_match[-1].strip()
        
    return "Sin registrar"

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

    # Caso Especial: "1 pago" (Pago Único)
    if "1 pago" in s or "un pago" in s:
        # Retornamos 0 semanas para indicar que se debe calcular por fechas
        return 0, total, "Unico"

    # Caso 1: Multiplicación explícita (ej: "110*19200") -> 110 Días * $19200 Diarios
    if '*' in s:
        parts = s.split('*')
        try:
            # Usar clean_money para las partes para ser robusto
            dias = clean_money(parts[0])
            diario = clean_money(parts[1])
            
            # Recalcular total si el Excel estaba vacío o mal
            # Prioridad: Si hay multiplicación, ese es el total real pactado
            total_calculado = dias * diario
            
            # VALIDACIÓN DE SEGURIDAD:
            # Si el total calculado es diferente al 'Monto Devolver' del Excel (ej: > 10% diff),
            # y el monto del Excel no es cero, confiamos en el Excel.
            # Esto corrige casos ambiguos como "160*36000" donde 36000 es semanal y no diario.
            if total_calculado > 0:
                if total > 0 and abs(total_calculado - total) > (total * 0.1):
                    print(f"⚠️ Discrepancia en Plan '{s}': Calc={total_calculado} vs Excel={total}. Usando Excel.")
                    # Si usamos el total del Excel, debemos ajustar las semanas para que el pago semanal tenga sentido
                    # O simplemente dejar el total del Excel.
                    # Si asumimos que el Excel es correcto, recalculamos semanas si es necesario?
                    # No, las semanas siguen siendo dias/5.
                else:
                    total = total_calculado
            
            # Convertir Días a Semanas (Divisor 5)
            semanas = dias / 5
            frecuencia = "Semanal" # El sistema base es semanal
            return semanas, total, frecuencia
        except:
            pass

    # Extraer número del plan
    # Usamos clean_money para sacar el número "4" de "4 meses" de forma segura
    # Pero clean_money busca el mayor, aquí queremos el número asociado a la palabra
    match = re.search(r'(\d+[\.,]?\d*)', s)
    if match:
        num = float(match.group(1).replace(',', '.'))
        
        if 'mes' in s:
            # 1 Mes = 4 Semanas (20 días hábiles / 5)
            semanas = num * 4
            frecuencia = "Mensual"
        elif 'quin' in s or 'q.' in s:
            # 1 Quincena = 2 Semanas (10 días hábiles / 5)
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
            domicilio_raw = str(row.get('Domicilio part. y laboral', '')).strip()
            
            # VALIDACIÓN EXTRA: Si 'Pendiente $$$' es NaN, es probable que sea una fila de totales o basura
            pendiente_check = row.get('Pendiente $$$')
            if pd.isna(pendiente_check):
                print(f"⚠️ Saltando fila {index+2} ({nombre}) - Columna 'Pendiente $$$' vacía (posible total o basura).")
                continue

            # Extraer teléfono del domicilio
            telefono = extract_phone(domicilio_raw)
            # Limpiar domicilio quitando el teléfono si es posible (opcional, por ahora lo dejamos completo)
            domicilio = domicilio_raw

            if not nombre or nombre.lower() == 'nan':
                continue
            
            if not dni or dni.lower() == 'nan':
                dni = f"S/D-{index}" # Generar DNI temporal si falta

            # Buscar o Crear Cliente
            # Lógica mejorada para detectar duplicados de DNI con diferente nombre
            cliente_existente = db.query(Cliente).filter(Cliente.dni == dni).first()
            
            if cliente_existente:
                # Si el DNI existe, verificar si el nombre coincide (fuzzy match simple)
                # Si los nombres son muy diferentes, es un conflicto de DNI (dos personas con mismo DNI en Excel)
                nombre_existente = cliente_existente.nombre.lower()
                nombre_nuevo = nombre.lower()
                
                # Verificar si es la misma persona (ej: "Juan Perez" vs "Juan A. Perez")
                # Si NO es la misma persona, generamos un DNI alternativo para el nuevo
                if nombre_nuevo not in nombre_existente and nombre_existente not in nombre_nuevo:
                    print(f"⚠️ CONFLICTO DNI DETECTADO: DNI {dni} pertenece a '{cliente_existente.nombre}', pero ahora viene '{nombre}'.")
                    print(f"   -> Generando DNI alternativo para '{nombre}' para permitir importación.")
                    dni = f"{dni}-{index}" # DNI único para evitar crash
                    cliente = None # Forzar creación de nuevo cliente
                else:
                    cliente = cliente_existente
            else:
                # Si no existe por DNI, buscar por nombre (por si cambió el DNI)
                cliente = db.query(Cliente).filter(Cliente.nombre == nombre).first()
                
            if not cliente:
                cliente = Cliente(
                    nombre=nombre,
                    dni=dni,
                    direccion=domicilio,
                    telefono=telefono,
                    fecha_registro=datetime.date.today()
                )
                db.add(cliente)
                db.commit()
                db.refresh(cliente)
                count_clientes += 1
            else:
                # Actualizar teléfono si no tenía
                if cliente.telefono == "Sin registrar" and telefono != "Sin registrar":
                    cliente.telefono = telefono
                    db.commit()
            
            # 2. Crédito
            try:
                monto_prestado = clean_money(row.get('Capital', 0))
                monto_devolver_excel = clean_money(row.get('Monto Devolver', 0))
                fecha_inicio = parse_date(row.get('Fecha Inicio del credito'))
                if not fecha_inicio:
                    fecha_inicio = datetime.date.today()
                
                # Intentar leer fecha final para cálculos precisos
                fecha_final_excel = parse_date(row.get('Fecha Final del credito'))

                # Calcular Semanas y Total usando lógica de Días Hábiles
                plan_str = str(row.get('Plan. Pagos', ''))
                semanas, monto_total, frecuencia = parse_plan_details(plan_str, monto_devolver_excel)
                
                # Si es "Unico" (1 pago), calcular semanas reales basadas en fechas
                if frecuencia == "Unico":
                    if fecha_final_excel and fecha_final_excel > fecha_inicio:
                        dias_totales = (fecha_final_excel - fecha_inicio).days
                        semanas = dias_totales / 7.0
                    else:
                        semanas = 4.0 # Default 1 mes si no hay fecha final
                
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
