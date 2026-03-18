from database import SessionLocal, Employee, SupplyRequest, RequestItem
from sqlalchemy.orm import joinedload

search_name = "VOPOROSO, MARIA"

with SessionLocal() as session:
    emp = session.query(Employee).filter(Employee.name.like(f"%{search_name}%")).first()
    if not emp:
        print(f"Employee {search_name} not found.")
    else:
        print(f"Employee: {emp.name} (ID: {emp.id})")
        # Fetch all requests
        requests = session.query(RequestItem).join(SupplyRequest).filter(
            SupplyRequest.employee_id == emp.id
        ).options(joinedload(RequestItem.supply_request)).all()
        
        print(f"Total History Items in DB: {len(requests)}")
        for r in requests:
            print(f"  - Item: {r.item_id}, Qty: {r.quantity}, Date: {r.supply_request.request_date}")

    # Also check total count of 'future' dates
    from datetime import datetime
    now = datetime(2026, 3, 18)
    future_count = session.query(SupplyRequest).filter(SupplyRequest.request_date > now).count()
    print(f"\nTotal Requests in the future (after 2026-03-18): {future_count}")
    
    if future_count > 0:
        samples = session.query(SupplyRequest).filter(SupplyRequest.request_date > now).limit(5).all()
        print("Sample future dates:")
        for s in samples:
            print(f"  - ID: {s.id}, Date: {s.request_date}")
