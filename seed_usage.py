from database import SessionLocal, Employee, Department, Item, SupplyRequest, RequestItem
from datetime import datetime, timedelta
import random

def seed_test_data():
    with SessionLocal() as session:
        # Get an existing employee or use a new one
        emp = session.query(Employee).first()
        dept = session.query(Department).first()
        item = session.query(Item).first()
        
        if not all([emp, dept, item]):
            print("Missing baseline data. Run the main app first.")
            return

        print(f"Adding 5 historical requests for {emp.name} to test usage gaps...")
        
        # Add 5 requests for the same item with 10-day gaps
        base_date = datetime(2026, 1, 1)
        for i in range(5):
            req_date = base_date + timedelta(days=i*10)
            req = SupplyRequest(
                employee_id=emp.id,
                department_id=dept.id,
                request_date=req_date
            )
            session.add(req)
            session.flush()
            
            ri = RequestItem(
                request_id=req.id,
                item_id=item.id,
                quantity=1.0,
                is_refill_request=False
            )
            session.add(ri)
        
        session.commit()
        print("Data seeded. Average days should be 10.0 in the report.")

if __name__ == "__main__":
    seed_test_data()
