import pandas as pd
import re

file_path = "datos_clientes.xlsx"
try:
    df = pd.read_excel(file_path)
    print("Columns:", df.columns.tolist())
    
    # Find row with 540000 in Acumulado $$
    col_acumulado = "Acumulado $$$"
    
    for index, row in df.iterrows():
        val_acum = str(row[col_acumulado])
        if "540000" == val_acum or "540000.0" == val_acum:
            print(f"--- Row {index} ---")
            print(f"Nombre: {row['Nombre y Apellido']}")
            print(f"Capital: {row['Capital']}")
            print(f"Monto Devolver: {row['Monto Devolver']}")
            print(f"Plan. Pagos: {row['Plan. Pagos']}")
            print(f"Acumulado $$$: {row['Acumulado $$$']}")
            print(f"Pendiente $$$: {row['Pendiente $$$']}")
            
            # Print payments
            print("Pagos:")
            for col in df.columns:
                if re.match(r'^\d{1,2}\.\d{1,2}\.\d{2,4}$', str(col)):
                    val = row[col]
                    if pd.notna(val) and val != 0:
                        print(f"  {col}: {val}")
            print("-" * 20)



except Exception as e:
    print(e)
