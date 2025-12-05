import pandas as pd
import re

file_path = "datos_clientes.xlsx"
try:
    df = pd.read_excel(file_path)
    print("Columns:", df.columns.tolist())
    
    # Check for valid clients with NaN Pendiente
    print("\n--- Clients with NaN Pendiente ---")
    count = 0
    for index, row in df.iterrows():
        nombre = str(row['Nombre y Apellido']).strip()
        pendiente = row['Pendiente $$$']
        if nombre and nombre.lower() != 'nan' and pd.isna(pendiente):
            print(f"Row {index}: {nombre} (Devolver: {row['Monto Devolver']})")
            count += 1
            if count > 10:
                print("... and more")
                break




except Exception as e:
    print(e)
