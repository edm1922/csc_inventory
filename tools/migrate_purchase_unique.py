import sqlite3
import os

# Define database path
current_dir = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.abspath(os.path.join(current_dir, "..", "data", "supply_system.db"))

def migrate():
    print(f"Starting database migration for purchase_requests in {DB_FILE}...")
    if not os.path.exists(DB_FILE):
        print("Database file doesn't exist yet, nothing to migrate.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION;")
        
        # 1. Rename existing purchase_requests table
        print("Renaming purchase_requests to purchase_requests_old...")
        cursor.execute("ALTER TABLE purchase_requests RENAME TO purchase_requests_old;")
        
        # 2. Create new table with updated constraints
        print("Creating new purchase_requests table...")
        cursor.execute("""
            CREATE TABLE purchase_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pr_no TEXT NOT NULL,
                request_date DATETIME,
                department TEXT,
                end_user TEXT,
                position TEXT,
                prepared_by TEXT,
                approved_by TEXT,
                status TEXT DEFAULT 'PENDING',
                UNIQUE(pr_no, request_date)
            );
        """)
        
        # 3. Copy data from purchase_requests_old to purchase_requests
        # Find all columns that exist in purchase_requests_old
        cursor.execute("PRAGMA table_info(purchase_requests_old)")
        old_cols = [c[1] for c in cursor.fetchall()]
        
        target_cols = ["id", "pr_no", "request_date", "department", "end_user", "position", "prepared_by", "approved_by", "status"]
        common_cols = [c for c in target_cols if c in old_cols]
        col_list = ", ".join(common_cols)
        
        print(f"Copying data for columns: {col_list}")
        cursor.execute(f"INSERT INTO purchase_requests ({col_list}) SELECT {col_list} FROM purchase_requests_old;")
        
        # 4. Drop the old table
        print("Dropping purchase_requests_old...")
        cursor.execute("DROP TABLE purchase_requests_old;")
        
        # 5. Re-create index if it was lost
        print("Creating index on id...")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_purchase_requests_id ON purchase_requests (id);")
        
        conn.commit()
        print("Migration complete!")
    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
