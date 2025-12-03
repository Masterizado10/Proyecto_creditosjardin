from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .database import Base
import datetime

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    direccion = Column(String)
    lugar_trabajo = Column(String, nullable=True)
    telefono = Column(String)
    dni = Column(String, unique=True, index=True)
    foto_perfil = Column(String, nullable=True)
    fecha_registro = Column(Date, default=datetime.date.today)

    creditos = relationship("Credito", back_populates="cliente", cascade="all, delete-orphan")
    notas = relationship("Nota", back_populates="cliente", cascade="all, delete-orphan")

class Credito(Base):
    __tablename__ = "creditos"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    monto_prestado = Column(Float)
    tasa_interes = Column(Float) # Porcentaje, ej: 10 para 10%
    monto_total = Column(Float)
    semanas = Column(Float) # Ahora representa "Plazo" (cantidad de periodos), puede ser decimal (ej. 14.4)
    frecuencia = Column(String, default="Semanal") # Semanal, Quincenal, Mensual
    pago_semanal = Column(Float) # Ahora representa "Pago por Periodo" (Cuota)
    fecha_inicio = Column(Date, default=datetime.date.today)
    recargos = Column(Float, default=0.0)
    activo = Column(Boolean, default=True)

    cliente = relationship("Cliente", back_populates="creditos")
    pagos = relationship("Pago", back_populates="credito", cascade="all, delete-orphan")

class Pago(Base):
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True)
    credito_id = Column(Integer, ForeignKey("creditos.id"))
    monto = Column(Float)
    fecha = Column(Date, default=datetime.date.today)
    nota = Column(String, nullable=True)

    credito = relationship("Credito", back_populates="pagos")

class Nota(Base):
    __tablename__ = "notas"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    texto = Column(String)
    fecha = Column(Date, default=datetime.date.today)

    cliente = relationship("Cliente", back_populates="notas")

# Actualizar relación en Cliente (monkey-patching o editar arriba si fuera posible, 
# pero para este flujo editaremos la clase Cliente arriba también si es necesario, 
# o simplemente definimos la relación inversa aquí si SQLAlchemy lo permite, 
# pero lo ideal es editar la clase Cliente).

