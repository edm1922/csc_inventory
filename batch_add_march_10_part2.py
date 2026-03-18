from database import SessionLocal, Employee, Item, SupplyRequest, RequestItem, Department
from datetime import datetime
import re

def batch_add_march_10_part2():
    data_text = """
1	CORNEJO, MELVIN	FOOT BATH MONITORER	BALLPEN	—	UNTIL DEFECTIVE
REFILL	—	2 WEEKS
2	RATUNIL, NEÑO	CHEMICAL/PEACOCK MONITORER	BALLPEN	—	UNTIL DEFECTIVE
LOGBOOK	—	(no frequency)
REFILL	—	2 WEEKS
3	RUIZ, NORLYN	ROLLER LINT MONITORER	BALLPEN	—	UNTIL DEFECTIVE
WHISTLE	—	UNTIL DEFECTIVE
REFILL	—	2 WEEKS
4	PAPASIN, VERONICA	HANDRIP MONITORER	BALLPEN	—	(no frequency)
LOGBOOK	—	UNTIL DEFECTIVE
WHISTLE	—	2 WEEKS
REFILL	—	UNTIL DEFECTIVE
5	PUSOD, DAVE	ROLLER LINT MONITORER	BALLPEN	—	UNTIL DEFECTIVE
CLIPBOARD	—	UNTIL DEFECTIVE
LOGBOOK	—	(no frequency)
WHISTLE	—	(no frequency)
REFILL	—	2 WEEKS
"""

    date_str = "2026-03-10"
    req_date = datetime.strptime(date_str, "%Y-%m-%d")
    shift = "603"
    area = "SANITATION TUNE 3"

    ITEM_MAP = {
        "BALLPEN": "BALLPEN HBW",
        "LOGBOOK": "LOGBOOK (RECORD BOOK)",
        "WHISTLE": "WHISTLE"
    }

    with SessionLocal() as session:
        all_emps = session.query(Employee).all()
        blocks = []
        current_block = None
        
        for line in data_text.strip().split("\n"):
            line = line.strip()
            if not line: continue
            
            # Start of a new person block
            match = re.match(r"^(\d+)\s+(.+?)\s+(FOOT BATH MONITORER|CHEMICAL/PEACOCK MONITORER|ROLLER LINT MONITORER|HANDRIP MONITORER)\s+(.+?)\s+(—|\d+)\s+(.+)$", line)
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
                    for req in current_block["requests"]:
                        if "BALLPEN" in req["item"]:
                            req["is_refill"] = True
                            parts = line.split("\t")
                            if len(parts) >= 3:
                                req["freq"] = parts[2].strip().upper()
                else:
                    sub_match = re.search(r"^(.+?)\s+(—|\d+)\s+(.+)$", line)
                    if sub_match:
                        current_block["requests"].append({
                            "item": sub_match.group(1).strip().upper(),
                            "qty": 1.0 if sub_match.group(2) == "—" else float(sub_match.group(2)),
                            "freq": sub_match.group(3).strip().upper(),
                            "is_refill": False
                        })

        if current_block: blocks.append(current_block)

        dept = session.query(Department).filter_by(area_name=area, shift=shift).first()
        if not dept:
            dept = Department(area_name=area, shift=shift, supervisor="N/A")
            session.add(dept)
            session.flush()

        for block in blocks:
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
                found_emp.role = block["role"]
            
            new_req = SupplyRequest(
                employee_id=found_emp.id,
                department_id=dept.id,
                request_date=req_date
            )
            session.add(new_req)
            session.flush()

            for r in block["requests"]:
                mapped_name = ITEM_MAP.get(r["item"], r["item"])
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
        print("Batch import (March 10 Part 2) complete.")

if __name__ == "__main__":
    batch_add_march_10_part2()
