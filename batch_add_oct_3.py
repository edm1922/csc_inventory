from database import SessionLocal, Employee, Item, SupplyRequest, RequestItem, Department
from datetime import datetime
import re

def batch_add_oct_3():
    data_text = """
1	CAORTE, RAVELO GIAN CARLO	FOOT BATH MONITORER	BALLPEN	—	UNTIL DEFECTIVE
CLIPBOARD	—	UNTIL DEFECTIVE
WHISTLE	—	UNTIL DEFECTIVE
REFILL	—	2 WEEKS
2	MAKASPE, ANDRES	TRAY WASHING MONITORER	BALLPEN	—	UNTIL DEFECTIVE
CALCULATOR	—	UNTIL DEFECTIVE
REFILL	—	2 WEEKS
3	MAKASPE, SADAM	TRAY WASHING MONITORER	BALLPEN	—	UNTIL DEFECTIVE
BROWN FOLDER	—	(no frequency specified)
REFILL	—	2 WEEKS
4	PACARDO, DAILYN	TRAY WASHING MONITORER	BALLPEN	—	(no frequency specified)
CALCULATOR	—	UNTIL DEFECTIVE
CLIPBOARD	—	2 WEEKS
LOGBOOK	—	UNTIL DEFECTIVE
REFILL	—	UNTIL DEFECTIVE
"""

    date_str = "2026-10-03" # 10-03-2026
    req_date = datetime.strptime(date_str, "%Y-%m-%d")
    shift = "603"
    area = "SANITATION TUNE 3"

    ITEM_MAP = {
        "BALLPEN": "BALLPEN HBW",
        "WHISTLE": "WHISTLE",
        "LOGBOOK": "LOGBOOK (RECORD BOOK)"
    }

    with SessionLocal() as session:
        # Get all employees once for matching
        all_emps = session.query(Employee).all()
        
        # Parse data into blocks per person
        blocks = []
        current_block = None
        
        for line in data_text.strip().split("\n"):
            line = line.strip()
            if not line: continue
            
            # Check if this is a new person start line (starts with number)
            match = re.match(r"^(\d+)\s+(.+?)\s+(FOOT BATH MONITORER|TRAY WASHING MONITORER)\s+(.+?)\s+(—|\d+)\s+(.+)$", line)
            if match:
                if current_block: blocks.append(current_block)
                current_block = {
                    "name": match.group(2).strip().upper(),
                    "role": match.group(3).strip().upper(),
                    "requests": [
                        {
                            "item": match.group(4).strip().upper(),
                            "qty": 1.0 if match.group(5) == "—" else float(match.group(5)),
                            "freq": match.group(6).strip().upper(),
                            "is_refill": False
                        }
                    ]
                }
            elif current_block:
                if line.startswith("REFILL"):
                    # Mark the preceding BALLPEN as refill
                    for req in current_block["requests"]:
                        if "BALLPEN" in req["item"]:
                            req["is_refill"] = True
                            # Also update frequency if present in refill line
                            refill_parts = line.split("\t")
                            if len(refill_parts) >= 3:
                                req["freq"] = refill_parts[2].strip().upper()
                else:
                    # e.g., CLIPBOARD	—	UNTIL DEFECTIVE
                    sub_match = re.match(r"^(.+?)\s+(—|\d+)\s+(.+)$", line)
                    if sub_match:
                        current_block["requests"].append({
                            "item": sub_match.group(1).strip().upper(),
                            "qty": 1.0 if sub_match.group(2) == "—" else float(sub_match.group(2)),
                            "freq": sub_match.group(3).strip().upper(),
                            "is_refill": False
                        })

        if current_block: blocks.append(current_block)

        # 2. Get or Create Department
        # Shift 603, Area SANITATION TUNE 3
        dept = session.query(Department).filter_by(area_name=area, shift=shift).first()
        if not dept:
            dept = Department(area_name=area, shift=shift, supervisor="N/A")
            session.add(dept)
            session.flush()

        # Process blocks
        for block in blocks:
            # 1. Match Employee
            target_name = block["name"].replace(",", "").replace(" ", "")
            found_emp = None
            for e in all_emps:
                db_name_clean = e.name.replace(",", "").replace(" ", "").upper()
                if db_name_clean == target_name:
                    found_emp = e
                    break
            
            if not found_emp:
                found_emp = Employee(name=block["name"], role=block["role"])
                session.add(found_emp)
                session.flush()
                print(f"Created new employee: {found_emp.name}")
            else:
                # Update role if it changed
                found_emp.role = block["role"]
            
            # 3. Create Supply Request
            new_req = SupplyRequest(
                employee_id=found_emp.id,
                department_id=dept.id,
                request_date=req_date
            )
            session.add(new_req)
            session.flush()

            # 4. Add Request Items
            for r in block["requests"]:
                # Map item name
                mapped_name = ITEM_MAP.get(r["item"], r["item"])
                
                # Fetch or Create Item
                item = session.query(Item).filter_by(name=mapped_name).first()
                if not item:
                    item = Item(name=mapped_name)
                    session.add(item)
                    session.flush()
                
                req_item = RequestItem(
                    request_id=new_req.id,
                    item_id=item.id,
                    quantity=r["qty"],
                    is_refill_request=r["is_refill"],
                    frequency=r["freq"]
                )
                session.add(req_item)
                print(f"  Added: {mapped_name} (Qty {r['qty']}, Refill: {r['is_refill']}) for {found_emp.name}")

        session.commit()
        print("Batch import (Oct 3) complete.")

if __name__ == "__main__":
    batch_add_oct_3()
