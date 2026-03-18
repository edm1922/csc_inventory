from database import SessionLocal, Item
from sqlalchemy import func

with SessionLocal() as session:
    print("--- ALL CALCULATOR ITEMS ---")
    items = session.query(Item).filter(func.upper(Item.name).like("%CALCULATOR%")).all()
    for it in items:
        print(f"ID: {it.id}, Name: '{it.name}', Desc: '{it.description}'")

    print("\n--- SCHEMA CHECK (SQLITE_MASTER) ---")
    from sqlalchemy import text
    result = session.execute(text("SELECT sql FROM sqlite_master WHERE name='items'")).fetchone()
    print(result[0])
