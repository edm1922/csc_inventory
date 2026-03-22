from database import SessionLocal, Employee, Item, SupplyRequest, RequestItem, Department
from datetime import datetime
import re

def batch_add_march_3():
    # Consolidated data for March 3, 2026
    data = [
        {"name": "ARELLANO, EMELY", "role": "MONITORER", "items": [("BALLPEN HBW", 1, ""), ("CALCULATOR", 1, ""), ("CLIPBOARD", 1, ""), ("MARKER (PERMANENT)", 1, ""), ("MARKER (WHITEBOARD)", 1, "")]},
        {"name": "AVERGONZADO, DINA", "role": "MONITORER", "items": [("CLIPBOARD", 1, ""), ("REFILL INK (PERMANENT)", 1, ""), ("MARKER (PERMANENT)", 1, ""), ("MARKER (WHITEBOARD)", 1, "")]},
        {"name": "BATACANDOLO, NIKKIE", "role": "MONITORER", "items": [("BALLPEN HBW", 1, ""), ("CLIPBOARD", 1, ""), ("REFILL INK (PERMANENT)", 1, ""), ("MARKER (PERMANENT)", 1, ""), ("MARKER (WHITEBOARD)", 1, "")]},
        {"name": "BETING, PRIMITIBA", "role": "MONITORER", "items": [("BALLPEN HBW", 1, ""), ("CALCULATOR", 1, ""), ("CLIPBOARD", 1, ""), ("MARKER (PERMANENT)", 1, ""), ("MARKER (WHITEBOARD)", 1, "")]},
        {"name": "BOHOLST, JUNELY", "role": "MONITORER", "items": [("BALLPEN HBW", 1, ""), ("CLIPBOARD", 1, ""), ("REFILL INK (PERMANENT)", 1, ""), ("MARKER (PERMANENT)", 1, ""), ("MARKER (WHITEBOARD)", 1, "")]},
        {"name": "DALAAS, IAN", "role": "MONITORER", "items": [("BALLPEN HBW", 1, ""), ("CLIPBOARD", 1, ""), ("MARKER (PERMANENT)", 1, "")]},
        {"name": "GONZALGO, SANNY JAY", "role": "MONITORER", "items": [("BALLPEN HBW", 1, ""), ("CALCULATOR", 1, ""), ("CLIPBOARD", 1, ""), ("MARKER (PERMANENT)", 1, ""), ("MARKER (WHITEBOARD)", 1, "")]},
        {"name": "KLATON, RODELYN", "role": "MONITORER", "items": [("BALLPEN HBW", 1, ""), ("CALCULATOR", 1, ""), ("CLIPBOARD", 1, ""), ("MARKER (PERMANENT)", 1, ""), ("MARKER (WHITEBOARD)", 1, "")]},
        {"name": "MOLINA, JESSA MARIE", "role": "MONITORER", "items": [("BALLPEN HBW", 1, ""), ("CALCULATOR", 1, ""), ("CLIPBOARD", 1, ""), ("MARKER (PERMANENT)", 1, ""), ("MARKER (WHITEBOARD)", 1, "")]},
        {"name": "MONTOY, EFRAIL", "role": "MONITORER", "items": [("BALLPEN HBW", 1, ""), ("CALCULATOR", 1, ""), ("CLIPBOARD", 1, ""), ("MARKER (PERMANENT)", 1, ""), ("MARKER (WHITEBOARD)", 1, "")]},
        {"name": "ONDOY, BONZ JEDDAH", "role": "MONITORER", "items": [("BALLPEN HBW", 1, ""), ("CALCULATOR", 1, ""), ("CLIPBOARD", 1, ""), ("MARKER (PERMANENT)", 1, ""), ("MARKER (WHITEBOARD)", 1, "")]},
        {"name": "GERONA, JAKE", "role": "MONITORER", "items": [("BALLPEN HBW", 1, ""), ("CALCULATOR", 1, ""), ("CLIPBOARD", 1, ""), ("MARKER (PERMANENT)", 1, ""), ("MARKER (WHITEBOARD)", 1, "")]},
        {"name": "HABERLE, FREDDIE JR.", "role": "TEAM LEADER", "items": [("BALLPEN HBW", 1, ""), ("MARKER (PERMANENT)", 1, ""), ("CALCULATOR", 1, "")]},
        {"name": "HABERLE, FREDDIE JR.", "role": "RECORDER", "items": [("LOGBOOK (RECORD BOOK)", 1, ""), ("LOGBOOK (RECORD BOOK)", 4, "")]},
        {"name": "ORDANIZA, ANNA JOY", "role": "RECORDER", "items": [("BALLPEN HBW", 1, ""), ("CORRECTION TAPE (SMALL)", 1, ""), ("LOGBOOK (RECORD BOOK)", 1, "")]},
        {"name": "ROXAS, AIMIE LOU", "role": "SORTER", "items": [("BALLPEN HBW", 1, ""), ("HIGHLIGHTER", 1, "")]},
        {"name": "JANOLA, MAYRA", "role": "SORTER", "items": [("BALLPEN HBW", 1, "")]},
        {"name": "ABARQUEZ, BARTE", "role": "STENCILER", "items": [("BALLPEN HBW", 1, ""), ("PAPER CUTTER (METAL)", 1, "")]},
        {"name": "ARRADO, MARVIN REY", "role": "STENCILER", "items": [("BALLPEN HBW", 1, ""), ("PAPER CUTTER (METAL)", 1, "")]},
        {"name": "ELICADO, JOAN CARLO", "role": "STENCILER", "items": [("BALLPEN HBW", 1, ""), ("PAPER CUTTER (METAL)", 1, "")]},
    ]

    date_str = "2026-03-03"
    req_date = datetime.strptime(date_str, "%Y-%m-%d")
    shift = "307"
    area = "CAN LABELLING WAREHOUSE"
    supervisor = "HABERLE, FREDDIE JR."

    with SessionLocal() as session:
        # Get or Create Department
        dept = session.query(Department).filter_by(area_name=area, shift=shift, supervisor=supervisor).first()
        if not dept:
            dept = Department(area_name=area, shift=shift, supervisor=supervisor)
            session.add(dept)
            session.flush()

        for entry in data:
            # 1. Get or Create Employee
            emp = session.query(Employee).filter(Employee.name.like(f"%{entry['name'].split(',')[0].strip()}%")).filter(Employee.name.like(f"%{entry['name'].split(',')[-1].strip()}%")).first()
            if not emp:
                emp = Employee(name=entry['name'], role=entry['role'])
                session.add(emp)
                session.flush()
                print(f"Created employee: {emp.name}")
            else:
                emp.role = entry['role']
                emp.name = entry['name'] # Update to full name if partially matched

            # 2. Create Supply Request Header
            supply_req = SupplyRequest(
                employee_id=emp.id,
                department_id=dept.id,
                request_date=req_date
            )
            session.add(supply_req)
            session.flush()

            # 3. Add Request Items
            for item_name, qty, freq in entry['items']:
                # Fetch or Create Item
                item = session.query(Item).filter_by(name=item_name).first()
                if not item:
                    item = Item(name=item_name)
                    session.add(item)
                    session.flush()
                
                req_item = RequestItem(
                    request_id=supply_req.id,
                    item_id=item.id,
                    quantity=float(qty),
                    is_refill_request=False,
                    frequency=freq
                )
                session.add(req_item)
                print(f"  Added: {item_name} for {emp.name}")

        session.commit()
        print("Batch import (March 3) complete.")

if __name__ == "__main__":
    batch_add_march_3()
