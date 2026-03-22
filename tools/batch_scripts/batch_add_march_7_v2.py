
import os
import sqlite3
from datetime import datetime
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from request_main import Employee, Department, Item, SupplyRequest, RequestItem

# Database setup
DB_FILE = "supply_system.db"
engine = create_engine(f"sqlite:///{DB_FILE}")
SessionLocal = sessionmaker(bind=engine)

def batch_add_march_7_v2():
    # Data from user request
    date_str = "2026-03-07"
    shift = "FO-NS"
    area = "TUNA 3 PACKING LOCAL"
    supervisor = "DALMACIO, ROGELIO"
    
    # Header info
    target_date = datetime.strptime(date_str, "%Y-%m-%d")

    # Mapping for item names to match database/existing items
    item_map = {
        "BALLPEN (BODY)": "BALLPEN HBW",
        "WHITEBOARD (BODY) PENTLE PEN": "MARKER (WHITEBOARD)",
        "INK (WHITE BOARD)": "MARKER (WHITEBOARD) REFILL",
        "REFILL BALLPEN": "BALLPEN REFILL",
        "CLIPBOARD": "CLIPBOARD",
        "EARPLUG": "EARPLUG"
    }

    # Data to process
    # Format: (Name, Role, ItemsList)
    # ItemsList format: [(ItemName, Qty or "—", Frequency, is_refill)]
    data = [
        ("PEREZ, MARICEL", "LEAD PERSON", [
            ("BALLPEN (BODY)", 0.0, "EVERY 6 MONTHS", False),
            ("WHITEBOARD (BODY) PENTLE PEN", 0.0, "EVERY 6 MONTHS", False),
            ("INK (WHITE BOARD)", 0.0, "MONTHLY", False),
            ("REFILL BALLPEN", 0.0, "TWICE A MONTH", True),
            ("CLIPBOARD", 0.0, "EVERY BRC AUDIT", False)
        ]),
        ("ESPINOSA, ARLENE", "CAN SORTER/NET WEIGHER", [
            ("BALLPEN (BODY)", 0.0, "EVERY 6 MONTHS", False),
            ("WHITEBOARD (BODY) PENTLE PEN", 0.0, "EVERY 6 MONTHS", False),
            ("REFILL BALLPEN", 0.0, "TWICE A MONTH", True),
            ("CLIPBOARD", 0.0, "EVERY BRC AUDIT", False),
            ("EARPLUG", 0.0, "EVERY 6 MONTHS", False)
        ]),
        ("GANZON JOCELYN", "LAGTIME MONITORER", [
            ("BALLPEN (BODY)", 0.0, "EVERY 6 MONTHS", False),
            ("REFILL BALLPEN", 0.0, "TWICE A MONTH", True),
            ("CLIPBOARD", 0.0, "EVERY BRC AUDIT", False)
        ]),
        ("DIAZ, NORMAN", "PILER", [("EARPLUG", 0.0, "EVERY 6 MONTHS", False)]),
        ("BERJA", "SIMIK OPERATOR", [("EARPLUG", 0.0, "EVERY 6 MONTHS", False)]),
        ("MATAS, MARK ANTHONY", "SIMIK OPERATOR", [("EARPLUG", 0.0, "EVERY 6 MONTHS", False)]),
        ("GELVERO JAY", "SIMIK OPERATOR", [("EARPLUG", 0.0, "EVERY 6 MONTHS", False)]),
        ("CAGANTES, ANDY", "SEAMER OPER", [("EARPLUG", 0.0, "EVERY 6 MONTHS", False)]),
        ("PALOMA JESSA", "SAUCE FINALIST", [("EARPLUG", 0.0, "EVERY 6 MONTHS", False)]),
    ]

    with SessionLocal() as session:
        try:
            # 1. Get or Create Department
            dept = session.query(Department).filter_by(area_name=area, shift=shift).first()
            if not dept:
                dept = Department(area_name=area, shift=shift, supervisor=supervisor)
                session.add(dept)
                session.flush()
            elif supervisor and not dept.supervisor:
                dept.supervisor = supervisor

            for emp_name, role, items in data:
                # 2. Get or Create Employee
                emp = session.query(Employee).filter_by(name=emp_name).first()
                if not emp:
                    emp = Employee(name=emp_name, role=role)
                    session.add(emp)
                    session.flush()
                else:
                    emp.role = role # Update role

                # 3. Create Supply Request Header
                new_request = SupplyRequest(
                    employee_id=emp.id,
                    department_id=dept.id,
                    request_date=target_date
                )
                session.add(new_request)
                session.flush()

                # 4. Create Request Items
                for item_name_raw, qty_raw, freq, is_refill in items:
                    item_name = item_map.get(item_name_raw, item_name_raw)
                    qty = 1.0 if qty_raw == 0.0 else qty_raw # Default to 1 if not specified
                    
                    # Get or Create Item
                    db_item = session.query(Item).filter_by(name=item_name).first()
                    if not db_item:
                        db_item = Item(name=item_name, requires_refill=is_refill)
                        session.add(db_item)
                        session.flush()
                    
                    req_item = RequestItem(
                        request_id=new_request.id,
                        item_id=db_item.id,
                        quantity=qty,
                        is_refill_request=is_refill,
                        frequency=freq
                    )
                    session.add(req_item)
            
            session.commit()
            print(f"Successfully added {len(data)} employee requests for {date_str} with frequencies.")

        except Exception as e:
            session.rollback()
            print(f"Error: {e}")

if __name__ == "__main__":
    batch_add_march_7_v2()
