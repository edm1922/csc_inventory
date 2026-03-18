from database import SessionLocal, SupplyRequest
from sqlalchemy import func

with SessionLocal() as session:
    # Check for any remaining 'future' dates
    future_reqs = session.query(SupplyRequest).filter(SupplyRequest.request_date > func.date('2026-06-01')).all()
    print(f"Total 'Future' Requests remaining: {len(future_reqs)}")
    
    # Check sample of corrected dates
    samples = session.query(SupplyRequest).order_by(SupplyRequest.request_date).limit(5).all()
    print("\nSample Dates in DB:")
    for s in samples:
        print(s.request_date)
