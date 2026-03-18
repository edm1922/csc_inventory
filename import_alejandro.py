import json
import os
import re
from datetime import datetime
from database import SessionLocal, Employee, Department, Item, SupplyRequest, RequestItem, Location, Stock

# Configuration
JSON_FILE = "Alejandro_sheet.json"

def parse_date(date_str):
    if not date_str:
        return datetime.utcnow()
    # Try MM-DD-YYYY
    try:
        return datetime.strptime(date_str, "%m-%d-%Y")
    except ValueError:
        pass
    # Try YYYY-MM-DD
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        pass
    return datetime.utcnow()

def parse_quantity(q_str):
    if q_str is None or q_str == "":
        return 1.0 # Default to 1 if missing but requested
    # Extract first number found
    match = re.search(r"(\d+(\.\d+)?)", str(q_str))
    if match:
        return float(match.group(1))
    return 1.0

def run_import():
    if not os.path.exists(JSON_FILE):
        print(f"Error: {JSON_FILE} not found.")
        return

    with open(JSON_FILE, "r") as f:
        data = json.load(f)

    with SessionLocal() as session:
        # Ensure Locations exist
        warehouse = session.query(Location).filter_by(name="WAREHOUSE").first()
        if not warehouse:
            warehouse = Location(name="WAREHOUSE")
            session.add(warehouse)
            session.flush()
            
        satellite = session.query(Location).filter_by(name="SATELLITE OFFICE").first()
        if not satellite:
            satellite = Location(name="SATELLITE OFFICE")
            session.add(satellite)
            session.flush()

        source_id = warehouse.id
        dest_id = satellite.id

        total_entries = len(data.get("extracted_data", []))
        print(f"Processing {total_entries} data blocks...")

        for block in data.get("extracted_data", []):
            date_str = block.get("date")
            req_date = parse_date(date_str)
            shift_val = block.get("shift") or "N/A"
            supervisor_val = block.get("supervisor") or "N/A"
            area_val = block.get("area") or "GENERAL"

            # Get or Create Department
            dept = session.query(Department).filter_by(
                area_name=area_val,
                shift=shift_val,
                supervisor=supervisor_val
            ).first()
            if not dept:
                dept = Department(area_name=area_val, shift=shift_val, supervisor=supervisor_val)
                session.add(dept)
                session.flush()

            for req in block.get("supply_requests", []):
                recipients_raw = req.get("recipient")
                if not recipients_raw:
                    continue # Skip entries without recipients (e.g. bulk lists)

                # Split multiple recipients if they are comma-separated
                recipients = [r.strip() for r in recipients_raw.replace("/", ",").split(",") if r.strip()]
                
                supplies = req.get("supplies") or "UNKNOWN"
                qty_val = parse_quantity(req.get("quantity"))
                freq_val = req.get("frequency") or "N/A"
                scope_val = req.get("scope_of_work") or "EMPLOYEE"
                
                is_refill = "REFILL" in supplies.upper()

                # Get or Create Item
                item = session.query(Item).filter_by(name=supplies).first()
                if not item:
                    item = Item(name=supplies)
                    session.add(item)
                    session.flush()

                for recipient_name in recipients:
                    # Get or Create Employee
                    emp = session.query(Employee).filter_by(name=recipient_name).first()
                    if not emp:
                        emp = Employee(name=recipient_name, role=scope_val)
                        session.add(emp)
                        session.flush()
                    
                    # Create Supply Request
                    # We create one request per item for simplicity, matching the main app's submission behavior
                    new_request = SupplyRequest(
                        request_date=req_date,
                        employee_id=emp.id,
                        department_id=dept.id,
                        source_location_id=source_id,
                        dest_location_id=dest_id,
                        status="OK" # Mark old history as already delivered
                    )
                    session.add(new_request)
                    session.flush()

                    request_item = RequestItem(
                        request_id=new_request.id,
                        item_id=item.id,
                        quantity=qty_val,
                        is_refill_request=is_refill,
                        frequency=freq_val
                    )
                    session.add(request_item)

        session.commit()
        print("Import completed successfully.")

if __name__ == "__main__":
    run_import()
