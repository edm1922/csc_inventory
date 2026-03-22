import pandas as pd
from datetime import datetime
from database import SessionLocal, Employee, SupplyRequest, Department, RequestItem

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

# 1. EXTRACT GOLD DATA
gold_map = {} # GoldName -> Role
for i in range(len(df)):
    row = df.iloc[i].tolist()
    pot_name = str(row[4]).strip() if pd.notna(row[4]) else ""
    if pot_name != "" and pot_name != "nan" and pot_name != "RECIPIENT":
        match = next((e for e in target_employees if e in pot_name or pot_name in e), None)
        if match:
            role = str(row[5]).strip() if pd.notna(row[5]) else "N/A"
            if match not in gold_map or (gold_map[match] == "N/A" and role != "N/A"):
                gold_map[match] = role

print(f"Extracted {len(gold_map)} gold roles.")

# 2. APPLY REPAIRS
with SessionLocal() as session:
    print("\n--- Repairing Employees (with Merging) ---")
    
    # We'll map everything to the 'GoldName'
    # Step A: Identify all duplicates and merge them
    for target_name in target_employees:
        # Find all employees that match this target name (case insensitive/partial)
        db_matches = session.query(Employee).filter(
            (Employee.name.like(f"%{target_name}%")) | 
            (Employee.name == target_name)
        ).all()
        
        # Also check for vice-versa (if db name is a substring of target)
        # SQLAlchemy doesn't do 'target_name.contains(Employee.name)' easily in one filter, 
        # so let's just get all and filter in Python for safety since table is small.
        all_emps = session.query(Employee).all()
        actually_matching = [e for e in all_emps if e.name in target_name or target_name in e.name]
        
        if len(actually_matching) > 0:
            # We pick the one with the exact name if it exists, otherwise the first one
            primary = next((e for e in actually_matching if e.name == target_name), actually_matching[0])
            
            # Update primary profile
            primary.name = target_name
            gold_role = gold_map.get(target_name)
            if gold_role and gold_role != "N/A":
                primary.role = gold_role
            
            # Merge others into primary
            for other in actually_matching:
                if other.id != primary.id:
                    print(f"Merging '{other.name}' (ID {other.id}) into '{primary.name}' (ID {primary.id})")
                    # Update all requests to point to primary
                    requests_to_move = session.query(SupplyRequest).filter_by(employee_id=other.id).all()
                    for req in requests_to_move:
                        req.employee_id = primary.id
                    
                    # Delete the duplicate employee record
                    session.delete(other)
            session.flush()

    print("\n--- Repairing Invalid Dates ---")
    requests = session.query(SupplyRequest).all()
    count_dates = 0
    for req in requests:
        d = req.request_date
        if d.year == 2026 and d.month >= 10:
            try:
                # Swap month and day
                # 2026-10-03 (Oct 3rd) -> 2026-03-10 (March 10th)
                new_date = datetime(2026, d.day, d.month, d.hour, d.minute, d.second)
                req.request_date = new_date
                count_dates += 1
            except ValueError:
                pass
    
    print(f"Corrected {count_dates} inverted dates.")
    
    session.commit()
    print("\nDatabase repair complete (Cleaned duplicates & Fixed dates).")
