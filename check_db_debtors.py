from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Cliente, Credito
from app.database import SQLALCHEMY_DATABASE_URL as DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("--- Top Debtors in DB ---")
creditos = db.query(Credito).all()
data = []
for c in creditos:
    pagado = sum([p.monto for p in c.pagos])
    restante = c.monto_total - pagado
    data.append({
        'id': c.id,
        'cliente': c.cliente.nombre,
        'dni': c.cliente.dni,
        'total': c.monto_total,
        'restante': restante
    })

# Sort by restante descending
data.sort(key=lambda x: x['restante'], reverse=True)

for d in data[:10]:
    print(f"Cliente: {d['cliente']} (DNI: {d['dni']}) | Deuda: ${d['restante']:,.2f} | Total Orig: ${d['total']:,.2f}")
