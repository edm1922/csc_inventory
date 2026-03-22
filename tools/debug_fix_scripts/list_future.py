from database import SessionLocal, Employee, SupplyRequest, RequestItem
from sqlalchemy.orm import joinedload
from datetime import datetime

with SessionLocal() as session:
    now = datetime(2026, 3, 18)
    future_reqs = session.query(SupplyRequest).options(
        joinedload(SupplyRequest.employee),
        joinedload(SupplyRequest.requested_items).joinedload(RequestItem.item)
    ).filter(SupplyRequest.request_date > now).all()
    
    print(f"Found {len(future_reqs)} future requests:\n")
    for req in future_reqs:
        items = ", ".join([ri.item.name for ri in req.requested_items])
        print(f"Employee: {req.employee.name}")
        print(f"  Date: {req.request_date}")
        print(f"  Items: {items}")
        print("-" * 20)
