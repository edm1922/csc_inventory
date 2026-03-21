import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, validates

# Setup Database connection
DB_FILE = "supply_system.db"
engine = create_engine(f"sqlite:///{DB_FILE}", echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# MODELS
class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    role = Column(String, nullable=True)

    requests = relationship("SupplyRequest", back_populates="employee", cascade="all, delete-orphan")

class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    stocks = relationship("Stock", back_populates="location")
    requests_as_source = relationship("SupplyRequest", foreign_keys="SupplyRequest.source_location_id", back_populates="source_location")
    requests_as_dest = relationship("SupplyRequest", foreign_keys="SupplyRequest.dest_location_id", back_populates="dest_location")

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    area_name = Column(String, nullable=False)
    shift = Column(String, nullable=True)
    supervisor = Column(String, nullable=True)
    role = Column(String, nullable=True)

    requests = relationship("SupplyRequest", back_populates="department")

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, default="", nullable=False)
    unit = Column(String, nullable=True)
    price = Column(Float, default=0.0)
    standard_stock = Column(Float, default=0.0)
    actual_stock = Column(Float, default=0.0)
    pending_order = Column(Float, default=0.0)
    requires_refill = Column(Boolean, default=False, nullable=False)
    
    # Relationship to Supplier
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier = relationship("Supplier", back_populates="items")

    request_items = relationship("RequestItem", back_populates="item", cascade="all, delete-orphan")
    stocks = relationship("Stock", back_populates="item", cascade="all, delete-orphan")

class Stock(Base):
    __tablename__ = "stocks"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    quantity = Column(Float, default=0.0, nullable=False)

    item = relationship("Item", back_populates="stocks")
    location = relationship("Location", back_populates="stocks")

class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, unique=True, nullable=False)
    contact_person = Column(String, nullable=True)
    contact_number = Column(String, nullable=True)
    address = Column(String, nullable=True)
    payment_mode = Column(String, nullable=True)

    items = relationship("Item", back_populates="supplier")

class SupplyRequest(Base):
    __tablename__ = "supply_requests"
    id = Column(Integer, primary_key=True, index=True)
    request_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    
    # Fulfillment Source and Delivery Destination
    source_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    dest_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    
    # Request Status
    status = Column(String, default="PENDING", nullable=False)

    employee = relationship("Employee", back_populates="requests")
    department = relationship("Department", back_populates="requests")
    source_location = relationship("Location", foreign_keys=[source_location_id], back_populates="requests_as_source")
    dest_location = relationship("Location", foreign_keys=[dest_location_id], back_populates="requests_as_dest")
    requested_items = relationship("RequestItem", back_populates="supply_request", cascade="all, delete-orphan")

class RequestItem(Base):
    __tablename__ = "request_items"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("supply_requests.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    is_refill_request = Column(Boolean, default=False, nullable=False)
    frequency = Column(String, nullable=True)

    supply_request = relationship("SupplyRequest", back_populates="requested_items")
    item = relationship("Item", back_populates="request_items")

    __table_args__ = (
        CheckConstraint('quantity > 0', name='check_quantity_positive'),
    )

    @validates("quantity")
    def validate_quantity(self, key, value):
        if value is None or value <= 0:
            raise ValueError("Quantity must be greater than zero.")
        return value

class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"
    id = Column(Integer, primary_key=True, index=True)
    pr_no = Column(String, unique=True, nullable=False)
    request_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    department = Column(String, nullable=False)
    end_user = Column(String, nullable=True)
    position = Column(String, nullable=True)
    prepared_by = Column(String, nullable=True)
    approved_by = Column(String, nullable=True)
    status = Column(String, default="PENDING")

    items = relationship("PurchaseItem", back_populates="purchase_request", cascade="all, delete-orphan")

class PurchaseItem(Base):
    __tablename__ = "purchase_items"
    id = Column(Integer, primary_key=True, index=True)
    pr_id = Column(Integer, ForeignKey("purchase_requests.id"), nullable=False)
    description = Column(String, nullable=False)
    purpose = Column(String, nullable=True)
    for_dept = Column(String, nullable=True)
    price = Column(Float, default=0.0)
    qty = Column(Float, default=0.0)
    unit = Column(String, nullable=True)
    total = Column(Float, default=0.0)

    purchase_request = relationship("PurchaseRequest", back_populates="items")

def parse_frequency(freq_str):
    """Converts frequency strings like '1 WEEK' or '1 MONTH' into a timedelta."""
    from datetime import timedelta
    import re
    if not freq_str: return None
    s = freq_str.upper().strip()
    
    # Extract number
    match = re.search(r'(\d+)', s)
    num = int(match.group(1)) if match else 1
    
    if "WEEK" in s:
        return timedelta(weeks=num)
    elif "MONTH" in s:
        return timedelta(days=num * 30)
    elif "DAY" in s:
        return timedelta(days=num)
    elif "YEAR" in s:
        return timedelta(days=num * 365)
    return None

def normalize_frequency(text):
    """Normalize frequency strings according to strict user rules."""
    if not text:
        return ""
    
    s = text.upper().strip()
    
    # 1. N/A -> blank
    if s == "N/A":
        return ""
        
    # 2. Correct UNTIL IT'S DEFECTIVE -> UNTIL DEFECTIVE
    if ("UNTIL" in s and "DEFECTIVE" in s) or (s == "UNTIL IT'S DEFECTIVE"):
        return "UNTIL DEFECTIVE"
    
    # 3. Remove "EVERY"
    if s.startswith("EVERY "):
        s = s[6:].strip()
        
    # 4. Handle "ONCE A WEEK", "TWICE A MONTH", etc.
    if ("ONCE" in s or "TWICE" in s or "THRICE" in s) and (" A " in s):
        return s

    # 5. Handle time-based units strictly
    import re
    # Look for a number and a unit (DAY, WEEK, MONTH, YEAR)
    time_pattern = r'(\d+)?\s*(DAY|WEEK|MONTH|YEAR)S?'
    match = re.search(time_pattern, s)
    
    if match:
        num = match.group(1)
        unit = match.group(2)
        if num:
            n = int(num)
            return f"{n} {unit}S" if n > 1 else f"{n} {unit}"
        else:
            # Just "WEEKS" or "WEEK" (Handle plurality loosely)
            if "S" in s:
                 return f"{unit}S"
            return unit

    return s

def init_db():
    """Create tables if they don't exist and handle migrations for existing columns"""
    Base.metadata.create_all(bind=engine)
    
    # Simple migration logic for existing items table
    import sqlite3
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Columns to add if they don't exist
    new_cols = [
        ("description", "TEXT DEFAULT ''"),
        ("unit", "TEXT"),
        ("price", "REAL DEFAULT 0.0"),
        ("standard_stock", "REAL DEFAULT 0.0"),
        ("actual_stock", "REAL DEFAULT 0.0"),
        ("pending_order", "REAL DEFAULT 0.0"),
        ("supplier_id", "INTEGER")
    ]
    
    for col_name, col_type in new_cols:
        try:
            cursor.execute(f"ALTER TABLE items ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to items table.")
        except sqlite3.OperationalError:
            # Column likely already exists
            pass
    
    conn.commit()
    
    # Migration for locations and stock
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS locations (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS stocks (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, location_id INTEGER NOT NULL, quantity REAL DEFAULT 0.0, FOREIGN KEY(item_id) REFERENCES items(id), FOREIGN KEY(location_id) REFERENCES locations(id))")
        
        # Seed default locations
        for loc in ["MAIN OFFICE", "WAREHOUSE"]:
            cursor.execute("INSERT OR IGNORE INTO locations (name) VALUES (?)", (loc,))
        
        # Add location columns to supply_requests
        try:
            cursor.execute("ALTER TABLE supply_requests ADD COLUMN source_location_id INTEGER REFERENCES locations(id)")
        except sqlite3.OperationalError: pass
        try:
            cursor.execute("ALTER TABLE supply_requests ADD COLUMN dest_location_id INTEGER REFERENCES locations(id)")
        except sqlite3.OperationalError: pass
        
        # Add status column to supply_requests
        try:
            cursor.execute("ALTER TABLE supply_requests ADD COLUMN status TEXT DEFAULT 'PENDING'")
            # We assume all past supply requests are already completed before we added this feature
            cursor.execute("UPDATE supply_requests SET status = 'OK' WHERE status = 'PENDING'")
        except sqlite3.OperationalError: pass
 
        # Create Purchase Request Tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pr_no TEXT UNIQUE NOT NULL,
                request_date DATETIME,
                department TEXT,
                end_user TEXT,
                position TEXT,
                prepared_by TEXT,
                approved_by TEXT,
                status TEXT DEFAULT 'PENDING'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pr_id INTEGER NOT NULL,
                description TEXT,
                purpose TEXT,
                for_dept TEXT,
                price REAL DEFAULT 0.0,
                qty REAL DEFAULT 0.0,
                unit TEXT,
                total REAL DEFAULT 0.0,
                FOREIGN KEY(pr_id) REFERENCES purchase_requests(id)
            )
        """)

        # Migration: Move Item.actual_stock to Stock table (defaulting to MAIN OFFICE)
        cursor.execute("SELECT id FROM locations WHERE name = 'MAIN OFFICE'")
        row = cursor.fetchone()
        if row:
            main_loc_id = row[0]
            cursor.execute("SELECT id, actual_stock FROM items")
            items_stock = cursor.fetchall()
            for item_id, stock in items_stock:
                # Check if stock entry already exists
                cursor.execute("SELECT id FROM stocks WHERE item_id = ? AND location_id = ?", (item_id, main_loc_id))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO stocks (item_id, location_id, quantity) VALUES (?, ?, ?)", (item_id, main_loc_id, stock))
        
    except Exception as e:
        print(f"Migration error: {e}")
 
    conn.commit()
    conn.close()
    print(f"Database setup/migration complete at {DB_FILE}")
 
if __name__ == "__main__":
    init_db()
