import pandas as pd
from datetime import datetime

excel_file = "REQUEST SUPPLIES.xlsx"
df = pd.read_excel(excel_file, sheet_name="MONITORING ", header=None)

target_employees = [
    "PARCON, MERZEL", "DELA CRUZ, JOSHUA", "FLOREZ, RENNELLE", "HORTILANO, CLAIRE", "SABALOSA, ANNELYN",
    "CANLIAN, JOHARLIE", "LABELLA, JAKE", "JACKOSALEM, ESMINA", "BRACE, ARLENE", "BERÑIL, JOY ANN",
    "BARON, CHRISTHOPER", "PLANTIG, JOSHUA", "OLID PERIGREIN", "PANERIO, MARVIN", "LABELLA GERELLE VIC", "ESCRIBANO MARIS",
    "FAILAN, RODELYN", "ANTOLAN, JUPHET", "PLAZOS, RICA", "QUIJANO, NELSON", "ABATOL, JOVELY",
    "COARTE, RAVELO GIAN CARLO", "MAKASPE, ANDRES", "MAKASPE, SADAM", "PACARDO, DAILYN",
    "CORNEJO, MELVIN"
]

results = []
current_area = "Unknown"
current_shift = "Unknown"
current_supervisor = "Unknown"
current_date = None

print("Scanning sheet for target employees...")

for i in range(len(df)):
    row = df.iloc[i].tolist()
    row_str = [str(x) for x in row]
    
    # Update context
    if 'DATE:' in row_str[0].upper():
        current_date = row[2]
    if 'SHIFT' in row_str[0].upper():
        current_shift = row[2]
    if 'AREA' in row_str[0].upper():
        current_area = row[2]
    # Note: Supervisor might be elsewhere or implied
    
    # Check for employee name in RECIPIENT column (index 4)
    pot_name = str(row[4]).strip() if pd.notna(row[4]) else ""
    # Check if this name is in our target list (handling potential trailing spaces)
    match = next((e for e in target_employees if e in pot_name or pot_name in e), None)
    
    if match and pot_name != "nan" and pot_name != "RECIPIENT":
        role = row[5] if pd.notna(row[5]) else "N/A"
        results.append({
            "Name": match,
            "FoundName": pot_name,
            "Role": role,
            "Area": current_area,
            "Shift": current_shift,
            "Date": current_date
        })

res_df = pd.DataFrame(results)
print("\nExtracted Gold Standard Data:")
print(res_df.to_string())
