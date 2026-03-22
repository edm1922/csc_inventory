
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

def batch_add_march_3_part3():
    # Data from user request
    date_str = "2026-03-03"
    shift = "307"
    area = "CAN LABELLING WAREHOUSE"
    supervisor = "HABERLE, FREDDIE JR."
    
    # Header info
    target_date = datetime.strptime(date_str, "%Y-%m-%d")

    # Mapping for item names to match database/existing items
    item_map = {
        "BALLPEN": "BALLPEN HBW",
        "CUTTER": "CUTTER"
    }

    # Data to process
    # Format: (Name, Role, ItemsList)
    # ItemsList format: [(ItemName, Qty, Frequency)]
    data = [
        ("MARIBAO, MARK JAY", "STENCILER", [("BALLPEN", 1, "3 MONTHS"), ("CUTTER", 1, "2 MONTHS")]),
        ("OCHANILLA, RICO", "STENCILER", [("BALLPEN", 1, "3 MONTHS"), ("CUTTER", 1, "2 MONTHS")]),
        ("PIGA, GILBERT", "STENCILER", [("BALLPEN", 1, "3 MONTHS"), ("CUTTER", 1, "2 MONTHS")]),
        ("TANAMAN JOHN LOYD", "STENCILER", [("BALLPEN", 1, "3 MONTHS"), ("CUTTER", 1, "3 MONTHS")]),
        ("PACIN, JOHN RAE", "OPERATOR", [("BALLPEN", 1, "3 MONTHS")]),
        ("SALLALOZA, RIZAMAE", "OPERATOR", [("BALLPEN", 1, "3 MONTHS")]),
        ("SUEL REY", "OPERATOR", [("BALLPEN", 1, "3 MONTHS")]),
        ("UTILINE JUSTIN BRYLE", "OPERATOR", [("BALLPEN", 1, "3 MONTHS")]),
        ("MAURO, BAESAC", "OPERATOR", [("BALLPEN", 1, "3 MONTHS")]),
        ("LITERAL ALLON", "OPERATOR", [("BALLPEN", 1, "3 MONTHS")]),
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
                for item_name_raw, qty, freq in items:
                    item_name = item_map.get(item_name_raw, item_name_raw)
                    
                    # Get or Create Item
                    db_item = session.query(Item).filter_by(name=item_name).first()
                    if not db_item:
                        db_item = Item(name=item_name, requires_refill=False)
                        session.add(db_item)
                        session.flush()
                    
                    req_item = RequestItem(
                        request_id=new_request.id,
                        item_id=db_item.id,
                        quantity=float(qty),
                        is_refill_request=False,
                        frequency=freq
                    )
                    session.add(req_item)
            
            session.commit()
            print(f"Successfully added {len(data)} employee requests for {date_str}")

        except Exception as e:
            session.rollback()
            print(f"Error: {e}")

if __name__ == "__main__":
    batch_add_march_3_part3()
