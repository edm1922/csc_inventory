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
current_date = None
current_recipient = None
current_role = None

for i in range(len(df)):
    row = df.iloc[i].tolist()
    row_str = [str(x) for x in row]
    
    # Update date/area context
    if 'DATE:' in row_str[0].upper():
        current_date = row[2]
    if 'SHIFT' in row_str[0].upper():
        current_shift = row[2]
    if 'AREA' in row_str[0].upper():
        current_area = row[2]
        
    # Header check - if we hit a header, reset recipient/role context
    if 'SUPPLIES' in row_str[1].upper() and 'RECIPIENT' in row_str[4].upper():
        current_recipient = None
        current_role = None
        continue

    # Update recipient/role if present
    pot_name = str(row[4]).strip() if pd.notna(row[4]) else ""
    if pot_name != "" and pot_name != "nan":
        current_recipient = pot_name
        current_role = str(row[5]).strip() if pd.notna(row[5]) else "N/A"
    
    if current_recipient:
        # Check if current_recipient is one of our target employees
        match = next((e for e in target_employees if e in current_recipient or current_recipient in e), None)
        if match:
             results.append({
                "GoldName": match,
                "ActualName": current_recipient,
                "Role": current_role,
                "Area": current_area,
                "Shift": current_shift,
                "Date": current_date
            })

# Drop duplicates to see the unique mappings
res_df = pd.DataFrame(results).drop_duplicates(subset=["GoldName", "Role", "Area"])
print("\nUnique Gold Standard mappings found:")
print(res_df.to_string())
