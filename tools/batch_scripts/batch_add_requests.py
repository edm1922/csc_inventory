from database import SessionLocal, Employee, Item, SupplyRequest, RequestItem, Department
from datetime import datetime
import re

def batch_add():
    data_text = """
1	ANDOG, KENELITA	LEAD PERSON	BALLPEN	2	1 MONTH
(Refill)	2 ballpens	per month
2	ARSENIO, MICHAEL	LEAD PERSON	BALLPEN	4	1 MONTH
STABILO	2	1 MONTH
(Refill)	4 ballpens	per month
3	ASURO, JUNIFER	MONETORER	BALLPEN	1	1 MONTH
(Refill)	1 ballpen	per month
4	BACUS, JOVELYN	MONITORER	BALLPEN	2	1 MONTH
(Refill)	2 ballpens	per month
5	BALEN, ANGEL	MONITORER	BALLPEN	3	1 MONTH
(Refill)	3 ballpens	per month
6	BALIGNOT, MARISSA	MONITORER	BALLPEN	4	1 MONTH
(Refill)	4 ballpens	per month
7	BANTAN, GINA	MONITORER	BALLPEN	2	1 MONTH
(Refill)	2 ballpens	per month
8	BASTO, JONALD	MONETORER	BALLPEN	2	1 MONTH
(Refill)	2 ballpens	per month
9	CABELLES, NOEL	MONETORER	BALLPEN	2	1 MONTH
(Refill)	2 ballpens	per month
10	CARDOZA, EMELIAN	LEAD PERSON	BALLPEN	2	1 MONTH
(Refill)	2 ballpens	per month
11	CARITOS, GRACE	LEAD PERSON	BALLPEN	4	1 MONTH
(Refill)	4 ballpens	per month
12	JUMUAD, RONILO	LEAD PERSON	BALLPEN	4	1 MONTH
(Refill)	4 ballpens	per month
13	PAGALAN, ANGELITO	MONITORER	BALLPEN	3	1 MONTH
PERMANENT INK	1 BOT	1 MONTH
WHITEBOARD INK	1 BOT	1 MONTH
(Refill)	3 ballpens	per month
14	ROSAROSO, MURPHY	MONETORER	BALLPEN	2	1 MONTH
(Refill)	2 ballpens	per month
15	SANAMA, SIELA MAE	MONITORER	BALLPEN	3	1 MONTH
(Refill)	3 ballpens	per month
16	SANDOVAL, APPLE JOY	LEAD PERSON	BALLPEN	2	1 MONTH
(Refill)	2 ballpens	per month
17	VIAGAN, MARY CRIS	MONITORER	BALLPEN	2	1 MONTH
(Refill)	2 ballpens	per month
18	VIRGO, ROJEA	LEAD PERSON	BALLPEN	2	1 MONTH
(Refill)	2 ballpens	per month
"""

    # Item Mapping
    ITEM_MAP = {
        "BALLPEN": "BALLPEN HBW",
        "STABILO": "STABILO",
        "PERMANENT INK": "REFILL INK (PERMANENT)",
        "WHITEBOARD INK": "REFILL INK (WHITEBOARD)"
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
            # e.g., "1	ANDOG, KENELITA	LEAD PERSON	BALLPEN	2	1 MONTH"
            match = re.match(r"^(\d+)\s+(.+?)\s+(LEAD PERSON|MONETORER|MONITORER)\s+(.+?)\s+(\d+)\s+(.+)$", line)
            if match:
                if current_block: blocks.append(current_block)
                current_block = {
                    "name": match.group(2).strip().upper(),
                    "role": match.group(3).strip().upper(),
                    "requests": [
                        {
                            "item": match.group(4).strip().upper(),
                            "qty": float(match.group(5)),
                            "freq": match.group(6).strip().upper(),
                            "is_refill": False
                        }
                    ]
                }
            elif current_block:
                # Sub line - either another item or a (Refill) note
                if "(Refill)" in line:
                    # Mark the corresponding item as refill
                    # Usually "3 ballpens" means the BALLPEN item
                    for req in current_block["requests"]:
                        if "BALLPEN" in req["item"]:
                            req["is_refill"] = True
                else:
                    # Another item line for the same person
                    # e.g., "STABILO	2	1 MONTH"
                    # e.g., "PERMANENT INK	1 BOT	1 MONTH"
                    sub_match = re.match(r"^(.+?)\s+(\d+)(\s+BOT)?\s+(.+)$", line)
                    if sub_match:
                        current_block["requests"].append({
                            "item": sub_match.group(1).strip().upper(),
                            "qty": float(sub_match.group(2)),
                            "freq": sub_match.group(4).strip().upper(),
                            "is_refill": False
                        })

        if current_block: blocks.append(current_block)

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
            
            # 2. Determine Department (Area/Supervisor)
            # If they exist, get latest. If not, default to "PRODUCTION"
            dept = session.query(Department).join(SupplyRequest).filter(SupplyRequest.employee_id == found_emp.id).order_by(SupplyRequest.request_date.desc()).first()
            if not dept:
                # Filter for "PRODUCTION" area or create default
                dept = session.query(Department).filter_by(area_name="PRODUCTION", shift="DAY", supervisor="N/A").first()
                if not dept:
                    dept = Department(area_name="PRODUCTION", shift="DAY", supervisor="N/A")
                    session.add(dept)
                    session.flush()

            # 3. Create Supply Request
            new_req = SupplyRequest(
                employee_id=found_emp.id,
                department_id=dept.id,
                request_date=datetime.now()
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
        print("Batch import complete.")

if __name__ == "__main__":
    batch_add()
