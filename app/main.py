from fastapi import FastAPI, Depends, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from . import models, database
import pandas as pd
from io import BytesIO
from datetime import date, datetime, timedelta
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib import colors
import shutil
import os

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

# Asegurar que existe el directorio de uploads en el directorio actual (fuera del paquete congelado)
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Montar la carpeta de uploads externa primero para que tenga prioridad
app.mount("/static/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
# Montar la carpeta static interna (para css, js, etc)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

import random

FRASES_BIENVENIDA = [
    "Bienvenido, Eduardo. ¡Que tengas un día productivo!",
    "Hola Eduardo, el éxito es la suma de pequeños esfuerzos.",
    "Bienvenido al sistema Créditos Jardín.",
    "Eduardo, hoy es un gran día para crecer.",
    "Gestión eficiente, resultados excelentes.",
    "Tu liderazgo inspira confianza.",
    "Organización y disciplina, claves del éxito."
]

# Nueva configuración detallada de planes
PLANES_CONFIG = {
    "Semanal": {
        "11": {"dias": 55, "factor": 1.92},
        "14.2": {"dias": 72, "factor": 2.16},
        "22": {"dias": 110, "factor": 2.64},
        "32": {"dias": 160, "factor": 2.88},
        "40": {"dias": 210, "factor": 3.12},
        "48": {"dias": 240, "factor": 3.375},
    },
    "Quincenal": {
        "6": {"factor": 1.92},
        "7": {"factor": 2.16},
        "11": {"factor": 2.64},
        "16": {"factor": 2.88},
        "20": {"factor": 3.12},
        "24": {"factor": 3.375},
    },
    "Mensual": {
        "4": {"factor": 2.16},
        "6": {"factor": 2.64},
        "8": {"factor": 2.88},
        "10": {"factor": 3.12},
        "12": {"factor": 3.375},
    }
}

def get_frase():
    return random.choice(FRASES_BIENVENIDA)

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request, db: Session = Depends(database.get_db)):
    clientes_db = db.query(models.Cliente).all()
    
    clientes_con_estado = []
    for c in clientes_db:
        # Verificar si tiene ALGUN crédito activo
        creditos_activos = db.query(models.Credito).filter(models.Credito.cliente_id == c.id, models.Credito.activo == True).all()
        
        estado = "Sin Crédito"
        if creditos_activos:
            # Si tiene al menos uno activo, verificamos si realmente le falta pagar
            # (Aunque el flag activo debería controlarlo, hacemos doble check o tomamos el estado del último)
            estado = "Activo"
            # Podríamos refinar esto para ver si hay atrasos en alguno
        
        clientes_con_estado.append({
            "id": c.id,
            "nombre": c.nombre,
            "dni": c.dni,
            "telefono": c.telefono,
            "foto_perfil": c.foto_perfil,
            "estado": estado
        })

    # Métricas Dashboard
    total_clientes = db.query(models.Cliente).count()
    total_prestado_historico = db.query(models.Credito).with_entities(func.sum(models.Credito.monto_prestado)).scalar() or 0
    total_cobrado_historico = db.query(models.Pago).with_entities(func.sum(models.Pago.monto)).scalar() or 0
    
    # Total a cobrar incluye recargos
    total_monto_original = db.query(models.Credito).with_entities(func.sum(models.Credito.monto_total)).scalar() or 0
    total_recargos = db.query(models.Credito).with_entities(func.sum(models.Credito.recargos)).scalar() or 0
    total_a_cobrar = total_monto_original + total_recargos
    
    por_cobrar = total_a_cobrar - total_cobrado_historico
    
    metrics = {
        "total_clientes": total_clientes,
        "total_prestado": total_prestado_historico,
        "total_cobrado": total_cobrado_historico,
        "por_cobrar": por_cobrar
    }
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "clientes": clientes_con_estado, 
        "metrics": metrics,
        "frase_bienvenida": get_frase()
    })

@app.get("/buscar", response_class=HTMLResponse)
def buscar_cliente(q: str, request: Request, db: Session = Depends(database.get_db)):
    clientes = db.query(models.Cliente).filter(
        or_(
            models.Cliente.nombre.ilike(f"%{q}%"),
            models.Cliente.dni.ilike(f"%{q}%")
        )
    ).all()
    
    # Recalcular métricas (o pasar vacías si no queremos mostrarlas en búsqueda)
    # Para consistencia visual, pasamos las mismas métricas globales
    total_clientes = db.query(models.Cliente).count()
    total_prestado_historico = db.query(models.Credito).with_entities(func.sum(models.Credito.monto_prestado)).scalar() or 0
    total_cobrado_historico = db.query(models.Pago).with_entities(func.sum(models.Pago.monto)).scalar() or 0
    total_a_cobrar = db.query(models.Credito).with_entities(func.sum(models.Credito.monto_total)).scalar() or 0
    por_cobrar = total_a_cobrar - total_cobrado_historico
    
    metrics = {
        "total_clientes": total_clientes,
        "total_prestado": total_prestado_historico,
        "total_cobrado": total_cobrado_historico,
        "por_cobrar": por_cobrar
    }

    return templates.TemplateResponse("index.html", {"request": request, "clientes": clientes, "metrics": metrics, "busqueda": q})

@app.get("/lista_clientes", response_class=HTMLResponse)
def lista_clientes(request: Request, db: Session = Depends(database.get_db)):
    clientes_db = db.query(models.Cliente).all()
    
    clientes_con_estado = []
    for c in clientes_db:
        # Verificar si tiene ALGUN crédito activo
        creditos_activos = db.query(models.Credito).filter(models.Credito.cliente_id == c.id, models.Credito.activo == True).all()
        
        estado = "Sin Crédito"
        if creditos_activos:
            estado = "Activo"
        
        clientes_con_estado.append({
            "id": c.id,
            "nombre": c.nombre,
            "dni": c.dni,
            "telefono": c.telefono,
            "direccion": c.direccion,
            "foto_perfil": c.foto_perfil,
            "estado": estado
        })
    
    return templates.TemplateResponse("lista_clientes.html", {
        "request": request, 
        "clientes": clientes_con_estado,
        "frase_bienvenida": get_frase()
    })

@app.post("/clientes/")
def create_cliente(
    nombre: str = Form(...),
    direccion: str = Form(...),
    lugar_trabajo: str = Form(None),
    telefono: str = Form(...),
    dni: str = Form(...),
    monto: float = Form(...),
    tasa: float = Form(0), # Ya no es relevante si usamos planes fijos, pero lo mantenemos por compatibilidad
    semanas: str = Form(...), # Plazo como string para soportar "14.2"
    frecuencia_pago: str = Form(...), # Nuevo campo
    db: Session = Depends(database.get_db)
):
    # 1. Crear el Cliente
    cliente = models.Cliente(
        nombre=nombre, 
        direccion=direccion, 
        lugar_trabajo=lugar_trabajo,
        telefono=telefono, 
        dni=dni
    )
    db.add(cliente)
    db.flush() # Genera el ID del cliente sin confirmar la transacción aún

    # 2. Calcular y Crear el Crédito
    frecuencia = frecuencia_pago
    plazo_label = semanas
    
    config_plan = PLANES_CONFIG.get(frecuencia, {}).get(plazo_label)
    
    factor = 0
    plazo_real = 0
    
    if config_plan:
        factor = config_plan["factor"]
        monto_total = monto * factor
        
        if frecuencia == "Semanal" and "dias" in config_plan:
            # Lógica precisa por días para Semanal
            dias_calendario = config_plan["dias"]
            diario = monto_total / dias_calendario
            pago_periodo = diario * 5 # 5 días hábiles
            plazo_real = monto_total / pago_periodo # Puede dar decimal, ej 14.4
        else:
            # Lógica estándar para otros
            plazo_real = float(plazo_label)
            pago_periodo = monto_total / plazo_real
    else:
        # Fallback manual
        factor = 1 + (tasa / 100)
        monto_total = monto * factor
        try:
            plazo_real = float(plazo_label)
        except:
            plazo_real = 1
        pago_periodo = monto_total / plazo_real

    credito = models.Credito(
        cliente_id=cliente.id,
        monto_prestado=monto,
        tasa_interes=factor, # Guardamos el factor multiplicador en lugar de la tasa %
        monto_total=monto_total,
        semanas=plazo_real, # Guardamos el plazo real calculado
        frecuencia=frecuencia,
        pago_semanal=pago_periodo # Guardamos la cuota en 'pago_semanal'
    )
    db.add(credito)

    # 3. Confirmar todo
    db.commit()
    db.refresh(cliente)
    
    return RedirectResponse(url="/", status_code=303)

@app.get("/exportar_excel")
def exportar_excel(db: Session = Depends(database.get_db)):
    # Obtener todos los créditos (activos e inactivos) para el reporte completo
    creditos = db.query(models.Credito).all()
    data = []
    
    for cred in creditos:
        cliente = cred.cliente
        
        # Cálculos de fechas
        fecha_inicio = cred.fecha_inicio
        fecha_final = fecha_inicio + timedelta(weeks=cred.semanas)
        cantidad_total_dias = (fecha_final - fecha_inicio).days
        
        # Cálculos de pagos
        pagos = db.query(models.Pago).filter(models.Pago.credito_id == cred.id).all()
        total_pagado = sum(p.monto for p in pagos)
        pendiente = cred.monto_total - total_pagado
        if pendiente < 0: pendiente = 0
        
        # Métricas de tiempo abonado (estimado)
        # Semanas abonadas = Total Pagado / Pago Semanal
        semanas_abonadas = 0
        if cred.pago_semanal > 0:
            semanas_abonadas = total_pagado / cred.pago_semanal
            
        semanas_pendientes = cred.semanas - semanas_abonadas
        if semanas_pendientes < 0: semanas_pendientes = 0
        
        dias_abonados = semanas_abonadas * 7
        dias_pendientes = cantidad_total_dias - dias_abonados
        if dias_pendientes < 0: dias_pendientes = 0
        
        meses_abonados = semanas_abonadas / 4
        meses_pendientes = semanas_pendientes / 4
        
        # Plan de Pagos String
        plan_pagos = f"{cred.semanas} semanas ${cred.monto_total:,.2f}"
        
        # Construir fila
        row = {
            "CTO": cred.id,
            "Nombre y Apellido": cliente.nombre,
            "Domicilio part. y laboral": f"{cliente.direccion} / {cliente.lugar_trabajo or 'N/A'}",
            "D.N.I": cliente.dni,
            "Fecha Inicio del credito": fecha_inicio,
            "Fecha Final del credito": fecha_final,
            "cantidad total de dias": cantidad_total_dias,
            "Dias Abonados": round(dias_abonados, 2),
            "Dias Pendientes": round(dias_pendientes, 2),
            "Plan. Pagos": plan_pagos,
            "Capital": cred.monto_prestado,
            "Monto Devolver": cred.monto_total,
            "Cuota Semanal": cred.pago_semanal,
            "Acumulado $$$": total_pagado,
            "Pendiente $$$": pendiente,
            "Semanas Abonadas": round(semanas_abonadas, 2),
            "Semanas Pendientes": round(semanas_pendientes, 2),
            "Mes abonado": round(meses_abonados, 2),
            "MES PENDIENTE": round(meses_pendientes, 2)
        }
        data.append(row)
    
    df = pd.DataFrame(data)
    stream = BytesIO()
    with pd.ExcelWriter(stream) as writer:
        df.to_excel(writer, index=False)
    
    stream.seek(0)
    
    headers = {
        'Content-Disposition': 'attachment; filename="reporte_creditos_completo.xlsx"'
    }
    return StreamingResponse(stream, headers=headers)

@app.get("/clientes/{cliente_id}", response_class=HTMLResponse)
def detalle_cliente(cliente_id: int, request: Request, db: Session = Depends(database.get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cliente:
        return RedirectResponse(url="/")
    
    # Obtener TODOS los créditos ordenados por fecha (más reciente primero)
    creditos_db = db.query(models.Credito).filter(models.Credito.cliente_id == cliente_id).order_by(models.Credito.id.desc()).all()
    
    creditos_data = []
    
    # Si no hay créditos, pasamos lista vacía
    
    for credito in creditos_db:
        pagos = db.query(models.Pago).filter(models.Pago.credito_id == credito.id).order_by(models.Pago.fecha.desc()).all()
        total_pagado = sum(p.monto for p in pagos)
        
        # Recargos
        recargos = credito.recargos or 0.0
        monto_total_con_recargos = credito.monto_total + recargos
        
        # Cálculos de atraso
        dias_transcurridos = (date.today() - credito.fecha_inicio).days
        
        # Calcular periodos transcurridos según frecuencia
        periodos_transcurridos = 0
        dias_por_periodo = 7 # Default Semanal
        
        if credito.frecuencia == "Quincenal":
            dias_por_periodo = 15
        elif credito.frecuencia == "Mensual":
            dias_por_periodo = 30
            
        periodos_transcurridos = dias_transcurridos // dias_por_periodo
        if periodos_transcurridos < 0: periodos_transcurridos = 0
        
        monto_esperado = periodos_transcurridos * credito.pago_semanal
        if monto_esperado > monto_total_con_recargos:
            monto_esperado = monto_total_con_recargos
            
        atraso = monto_esperado - total_pagado
        restante = monto_total_con_recargos - total_pagado
        
        estado = "Activo"
        if restante <= 0.1: # Margen de error flotante
            estado = "Finalizado"
            restante = 0
            atraso = 0
            # Actualizar estado en DB si es necesario
            if credito.activo:
                credito.activo = False
                db.commit()
        else:
            # Si hay deuda (restante > 0.1), asegurar que el crédito esté Activo
            if not credito.activo:
                credito.activo = True
                db.commit()
        
        proximo_vencimiento = None
        if estado == "Activo":
            proximo_vencimiento = credito.fecha_inicio + timedelta(days=(periodos_transcurridos + 1) * dias_por_periodo)

        # Calcular fecha final estimada
        fecha_final = credito.fecha_inicio + timedelta(weeks=credito.semanas)

        # Cálculos de Días (Lógica solicitada: Acumulado * Días Hábiles / Cuota)
        # Definir días hábiles según frecuencia (Coincidente con lógica frontend)
        dias_habiles_periodo = 5 # Default Semanal
        if credito.frecuencia == "Quincenal":
            dias_habiles_periodo = 10
        elif credito.frecuencia == "Mensual":
            dias_habiles_periodo = 20

        dias_abonados = 0
        cantidad_total_dias = 0
        costo_diario = 0
        
        if credito.pago_semanal > 0:
            # Costo Diario = Cuota / Días Hábiles
            costo_diario = credito.pago_semanal / dias_habiles_periodo

            # Días Abonados = (Total Pagado * Días Hábiles) / Cuota del Periodo
            dias_abonados = (total_pagado * dias_habiles_periodo) / credito.pago_semanal
            
            # Cantidad Total de Días = (Monto Total * Días Hábiles) / Cuota del Periodo
            cantidad_total_dias = (monto_total_con_recargos * dias_habiles_periodo) / credito.pago_semanal
        else:
            # Fallback si no hay cuota definida
            cantidad_total_dias = (fecha_final - credito.fecha_inicio).days
            if monto_total_con_recargos > 0:
                dias_abonados = (total_pagado / monto_total_con_recargos) * cantidad_total_dias

        dias_pendientes = cantidad_total_dias - dias_abonados
        if dias_pendientes < 0: dias_pendientes = 0

        porcentaje = 0
        if monto_total_con_recargos > 0:
            porcentaje = int((total_pagado / monto_total_con_recargos) * 100)
            if porcentaje > 100: porcentaje = 100

        resumen = {
            "pagado": total_pagado,
            "restante": restante,
            "deberia_llevar": monto_esperado,
            "atraso": max(0, atraso),
            "porcentaje": porcentaje,
            "proximo_vencimiento": proximo_vencimiento,
            "estado": estado,
            "recargos": recargos,
            "monto_total_final": monto_total_con_recargos,
            "fecha_final": fecha_final,
            "cantidad_total_dias": round(cantidad_total_dias),
            "dias_abonados": round(dias_abonados),
            "dias_pendientes": round(dias_pendientes),
            "costo_diario": costo_diario
        }
        
        creditos_data.append({
            "credito": credito,
            "pagos": pagos,
            "resumen": resumen
        })

    notas = db.query(models.Nota).filter(models.Nota.cliente_id == cliente_id).order_by(models.Nota.fecha.desc()).all()

    return templates.TemplateResponse("detalle_cliente.html", {
        "request": request, 
        "cliente": cliente, 
        "creditos_data": creditos_data, # Lista de créditos
        "notas": notas,
        "hoy": date.today(),
        "frase_bienvenida": get_frase()
    })

@app.post("/creditos/")
def create_credito_adicional(
    cliente_id: int = Form(...),
    monto: float = Form(...),
    tasa: float = Form(0),
    semanas: str = Form(...),
    frecuencia_pago: str = Form(...),
    db: Session = Depends(database.get_db)
):
    frecuencia = frecuencia_pago
    plazo_label = semanas
    
    config_plan = PLANES_CONFIG.get(frecuencia, {}).get(plazo_label)
    
    factor = 0
    plazo_real = 0
    
    if config_plan:
        factor = config_plan["factor"]
        monto_total = monto * factor
        
        if frecuencia == "Semanal" and "dias" in config_plan:
            dias_calendario = config_plan["dias"]
            diario = monto_total / dias_calendario
            pago_periodo = diario * 5
            plazo_real = monto_total / pago_periodo
        else:
            plazo_real = float(plazo_label)
            pago_periodo = monto_total / plazo_real
    else:
        factor = 1 + (tasa / 100)
        monto_total = monto * factor
        try:
            plazo_real = float(plazo_label)
        except:
            plazo_real = 1
        pago_periodo = monto_total / plazo_real

    credito = models.Credito(
        cliente_id=cliente_id,
        monto_prestado=monto,
        tasa_interes=factor,
        monto_total=monto_total,
        semanas=plazo_real,
        frecuencia=frecuencia,
        pago_semanal=pago_periodo,
        activo=True
    )
    db.add(credito)
    db.commit()
    
    return RedirectResponse(url=f"/clientes/{cliente_id}", status_code=303)

@app.post("/creditos/update")
def update_credito(
    credito_id: int = Form(...),
    monto: float = Form(...),
    tasa: float = Form(0),
    semanas: str = Form(...),
    frecuencia_pago: str = Form(...),
    db: Session = Depends(database.get_db)
):
    credito = db.query(models.Credito).filter(models.Credito.id == credito_id).first()
    if not credito:
        return RedirectResponse(url="/")

    # Recalcular valores
    frecuencia = frecuencia_pago
    plazo_label = semanas
    
    config_plan = PLANES_CONFIG.get(frecuencia, {}).get(plazo_label)
    
    factor = 0
    plazo_real = 0
    
    if config_plan:
        factor = config_plan["factor"]
        monto_total = monto * factor
        
        if frecuencia == "Semanal" and "dias" in config_plan:
            dias_calendario = config_plan["dias"]
            diario = monto_total / dias_calendario
            pago_periodo = diario * 5
            plazo_real = monto_total / pago_periodo
        else:
            plazo_real = float(plazo_label)
            pago_periodo = monto_total / plazo_real
    else:
        factor = 1 + (tasa / 100)
        monto_total = monto * factor
        try:
            plazo_real = float(plazo_label)
        except:
            plazo_real = 1
        pago_periodo = monto_total / plazo_real

    # Actualizar objeto crédito
    credito.monto_prestado = monto
    credito.tasa_interes = factor
    credito.monto_total = monto_total
    credito.semanas = plazo_real
    credito.frecuencia = frecuencia
    credito.pago_semanal = pago_periodo
    
    # Validar estado tras cambios (si ya se pagó algo, ver si sigue activo)
    total_pagado = db.query(func.sum(models.Pago.monto)).filter(models.Pago.credito_id == credito.id).scalar() or 0
    deuda_total = credito.monto_total + (credito.recargos or 0)
    
    if total_pagado >= (deuda_total - 0.1):
        credito.activo = False
    else:
        credito.activo = True

    db.commit()
    
    return RedirectResponse(url=f"/clientes/{credito.cliente_id}", status_code=303)

@app.post("/creditos/{credito_id}/delete")
def delete_credito(credito_id: int, db: Session = Depends(database.get_db)):
    credito = db.query(models.Credito).filter(models.Credito.id == credito_id).first()
    if credito:
        cliente_id = credito.cliente_id
        # Eliminar pagos asociados primero (aunque cascade debería hacerlo, es mejor ser explícito si no está configurado)
        db.query(models.Pago).filter(models.Pago.credito_id == credito_id).delete()
        db.delete(credito)
        db.commit()
        return RedirectResponse(url=f"/clientes/{cliente_id}", status_code=303)
    return RedirectResponse(url="/")

@app.post("/creditos/{credito_id}/recargo")
def agregar_recargo(
    credito_id: int,
    monto_recargo: float = Form(...),
    db: Session = Depends(database.get_db)
):
    credito = db.query(models.Credito).filter(models.Credito.id == credito_id).first()
    if credito:
        credito.recargos = (credito.recargos or 0.0) + monto_recargo
        db.commit()
        return RedirectResponse(url=f"/clientes/{credito.cliente_id}", status_code=303)
    return RedirectResponse(url="/")

@app.post("/notas/")
def create_nota(
    cliente_id: int = Form(...),
    texto: str = Form(...),
    db: Session = Depends(database.get_db)
):
    nota = models.Nota(cliente_id=cliente_id, texto=texto)
    db.add(nota)
    db.commit()
    return RedirectResponse(url=f"/clientes/{cliente_id}", status_code=303)

@app.post("/clientes/update")
def update_cliente(
    cliente_id: int = Form(...),
    nombre: str = Form(...),
    dni: str = Form(...),
    telefono: str = Form(...),
    direccion: str = Form(...),
    lugar_trabajo: str = Form(None),
    db: Session = Depends(database.get_db)
):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if cliente:
        cliente.nombre = nombre
        cliente.dni = dni
        cliente.telefono = telefono
        cliente.direccion = direccion
        cliente.lugar_trabajo = lugar_trabajo
        db.commit()
    return RedirectResponse(url=f"/clientes/{cliente_id}", status_code=303)

@app.post("/clientes/{cliente_id}/foto")
async def upload_foto_cliente(
    cliente_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db)
):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cliente:
        return RedirectResponse(url="/")
    
    # Guardar archivo
    file_extension = file.filename.split(".")[-1]
    filename = f"cliente_{cliente_id}_{datetime.now().timestamp()}.{file_extension}"
    # Guardar en el directorio externo de uploads
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Actualizar DB (la URL sigue siendo /static/uploads/...)
    cliente.foto_perfil = f"/static/uploads/{filename}"
    db.commit()
    
    return RedirectResponse(url=f"/clientes/{cliente_id}", status_code=303)

@app.post("/admin/foto")
async def upload_foto_admin(
    file: UploadFile = File(...)
):
    # Guardar como admin.jpg (o png, etc) fijo para simplificar
    file_path = os.path.join(UPLOAD_DIR, "admin_avatar.jpg")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return RedirectResponse(url="/", status_code=303)

@app.post("/clientes/{cliente_id}/delete")
def delete_cliente(cliente_id: int, db: Session = Depends(database.get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if cliente:
        db.delete(cliente)
        db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/pagos/")
def create_pago(
    cliente_id: int = Form(...),
    credito_id: int = Form(...),
    monto: float = Form(...),
    fecha: str = Form(...),
    db: Session = Depends(database.get_db)
):
    fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    
    pago = models.Pago(
        credito_id=credito_id,
        monto=monto,
        fecha=fecha_obj
    )
    db.add(pago)
    db.commit()
    
    return RedirectResponse(url=f"/clientes/{cliente_id}", status_code=303)

@app.post("/pagos/update")
def update_pago(
    pago_id: int = Form(...),
    monto: float = Form(...),
    fecha: str = Form(...),
    nota: str = Form(None),
    db: Session = Depends(database.get_db)
):
    pago = db.query(models.Pago).filter(models.Pago.id == pago_id).first()
    if pago:
        pago.monto = monto
        pago.fecha = datetime.strptime(fecha, "%Y-%m-%d").date()
        pago.nota = nota
        db.commit()
        
        # Recalcular estado del crédito tras la modificación
        credito = pago.credito
        total_pagado = db.query(func.sum(models.Pago.monto)).filter(models.Pago.credito_id == credito.id).scalar() or 0
        deuda_total = credito.monto_total + (credito.recargos or 0)
        
        if total_pagado < (deuda_total - 0.1):
            if not credito.activo:
                credito.activo = True
        else:
            if credito.activo:
                credito.activo = False
        db.commit()

        return RedirectResponse(url=f"/clientes/{pago.credito.cliente_id}", status_code=303)
    return RedirectResponse(url="/")

@app.get("/pagos/{pago_id}/recibo")
def descargar_recibo(pago_id: int, db: Session = Depends(database.get_db)):
    pago = db.query(models.Pago).filter(models.Pago.id == pago_id).first()
    if not pago:
        return RedirectResponse(url="/")
    
    credito = pago.credito
    cliente = credito.cliente
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Diseño del Recibo
    c.setLineWidth(2)
    c.rect(0.5 * inch, 6 * inch, 7.5 * inch, 4.5 * inch)
    
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(4.25 * inch, 9.8 * inch, "CRÉDITOS JARDÍN")
    
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(4.25 * inch, 9.4 * inch, "RECIBO DE PAGO")
    
    c.setFont("Helvetica", 12)
    c.drawString(1 * inch, 8.8 * inch, f"Fecha: {pago.fecha.strftime('%d/%m/%Y')}")
    c.drawString(5 * inch, 8.8 * inch, f"Recibo N°: {pago.id:06d}")
    
    c.line(1 * inch, 8.6 * inch, 7.5 * inch, 8.6 * inch)
    
    c.setFont("Helvetica", 14)
    c.drawString(1 * inch, 8 * inch, f"Recibí de: {cliente.nombre}")
    c.drawString(1 * inch, 7.5 * inch, f"La cantidad de: ${pago.monto:,.2f}")
    c.drawString(1 * inch, 7 * inch, f"Concepto: Abono a crédito #{credito.id}")
    
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(4.25 * inch, 6.5 * inch, "Gracias por su pago puntual.")
    
    c.save()
    buffer.seek(0)
    
    headers = {
        'Content-Disposition': f'attachment; filename="recibo_{pago_id}.pdf"'
    }
    return StreamingResponse(buffer, media_type='application/pdf', headers=headers)

@app.get("/creditos/{credito_id}/estado_cuenta")
def descargar_estado_cuenta(credito_id: int, db: Session = Depends(database.get_db)):
    credito = db.query(models.Credito).filter(models.Credito.id == credito_id).first()
    if not credito:
        return RedirectResponse(url="/")
    
    cliente = credito.cliente
    pagos = db.query(models.Pago).filter(models.Pago.credito_id == credito.id).order_by(models.Pago.fecha).all()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom Styles
    styles.add(ParagraphStyle(name='HeaderTitle', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=22, spaceAfter=10, fontName='Helvetica-Bold', textColor=colors.darkgreen))
    styles.add(ParagraphStyle(name='SubHeader', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12, spaceAfter=20, textColor=colors.gray))
    styles.add(ParagraphStyle(name='TableLabel', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='TableValue', parent=styles['Normal'], fontSize=10))
    
    # Header
    elements.append(Paragraph("CRÉDITOS JARDÍN", styles['HeaderTitle']))
    elements.append(Paragraph("Estado de Cuenta Detallado", styles['SubHeader']))
    elements.append(Spacer(1, 12))
    
    # Client Info Section
    data_cliente = [
        [Paragraph("<b>Cliente:</b>", styles['TableLabel']), Paragraph(cliente.nombre, styles['TableValue']), Paragraph("<b>Crédito #:</b>", styles['TableLabel']), Paragraph(str(credito.id), styles['TableValue'])],
        [Paragraph("<b>DNI:</b>", styles['TableLabel']), Paragraph(cliente.dni, styles['TableValue']), Paragraph("<b>Fecha Inicio:</b>", styles['TableLabel']), Paragraph(credito.fecha_inicio.strftime('%d/%m/%Y'), styles['TableValue'])],
        [Paragraph("<b>Dirección:</b>", styles['TableLabel']), Paragraph(cliente.direccion or "N/A", styles['TableValue']), Paragraph("<b>Estado:</b>", styles['TableLabel']), Paragraph("Activo" if credito.activo else "Finalizado", styles['TableValue'])]
    ]
    
    t_cliente = Table(data_cliente, colWidths=[1*inch, 2.5*inch, 1*inch, 2.5*inch])
    t_cliente.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
    ]))
    elements.append(t_cliente)
    elements.append(Spacer(1, 20))
    
    # Financial Summary
    total_pagado = sum(p.monto for p in pagos)
    recargos = credito.recargos or 0.0
    monto_total_final = credito.monto_total + recargos
    saldo_restante = monto_total_final - total_pagado
    if saldo_restante < 0: saldo_restante = 0
    
    elements.append(Paragraph("Resumen Financiero", styles['Heading3']))
    
    data_resumen = [
        ["Concepto", "Monto"],
        ["Monto Prestado (Capital)", f"${credito.monto_prestado:,.2f}"],
        ["Intereses y Cargos Administrativos", f"${(credito.monto_total - credito.monto_prestado):,.2f}"],
        ["Recargos por Mora", f"${recargos:,.2f}"],
        ["MONTO TOTAL A PAGAR", f"${monto_total_final:,.2f}"],
        ["Total Abonado a la Fecha", f"${total_pagado:,.2f}"],
        ["SALDO PENDIENTE", f"${saldo_restante:,.2f}"]
    ]
    
    t_resumen = Table(data_resumen, colWidths=[5*inch, 2*inch])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), colors.darkgreen),
        ('TEXTCOLOR', (0,0), (1,0), colors.white),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'), # Bold last row
        ('BACKGROUND', (0,-1), (-1,-1), colors.whitesmoke),
        ('TEXTCOLOR', (0,-1), (-1,-1), colors.darkred),
    ]))
    elements.append(t_resumen)
    elements.append(Spacer(1, 20))
    
    # Payments History
    elements.append(Paragraph("Historial de Pagos", styles['Heading3']))
    
    data_pagos = [["Fecha", "Monto Abonado", "Saldo Restante (Estimado)"]]
    
    saldo_temp = monto_total_final
    for pago in pagos:
        saldo_temp -= pago.monto
        data_pagos.append([
            pago.fecha.strftime('%d/%m/%Y'),
            f"${pago.monto:,.2f}",
            f"${max(0, saldo_temp):,.2f}"
        ])
        
    if not pagos:
        data_pagos.append(["-", "Sin pagos registrados", "-"])
        
    t_pagos = Table(data_pagos, colWidths=[2.5*inch, 2.5*inch, 2*inch])
    t_pagos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.gray),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.whitesmoke]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
    ]))
    elements.append(t_pagos)
    
    # Footer
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("Documento generado automáticamente por el sistema Créditos Jardín.", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    headers = {
        'Content-Disposition': f'attachment; filename="estado_cuenta_{credito_id}.pdf"'
    }
    return StreamingResponse(buffer, media_type='application/pdf', headers=headers)
