import sqlite3
import os

DB_FILE = "supply_system.db"

def migrate():
    print("Starting database migration to remove unique name constraint on items...")
    if not os.path.exists(DB_FILE):
        print("Database file doesn't exist yet, nothing to migrate.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if we have a unique index on 'name'
    cursor.execute("PRAGMA index_list(items)")
    indices = cursor.fetchall()
    unique_index_name = None
    for idx in indices:
        if idx[2] == 1: # 'unique' == 1
            # Check if this index is for the 'name' column
            cursor.execute(f"PRAGMA index_info({idx[1]})")
            cols = cursor.fetchall()
            if any(c[2] == 'name' for c in cols):
                unique_index_name = idx[1]
                break

    if not unique_index_name:
        print("No unique index on 'name' found. Migration might have already been done or table is empty/new.")
        conn.close()
        return

    print(f"Dropping unique constraint (index: {unique_index_name})...")
    
    # SQLite requires recreating the table to remove 'UNIQUE' constraint if it was part of CREATE TABLE
    # If it was a separate CREATE UNIQUE INDEX, we could just DROP INDEX.
    # But SQLAlchemy names them 'sqlite_autoindex_items_1', which cannot be dropped.
    
    try:
        cursor.execute("BEGIN TRANSACTION;")
        
        # 1. Rename existing items table
        cursor.execute("ALTER TABLE items RENAME TO items_old;")
        
        # 2. Get the CREATE statement for items_old but without UNIQUE(name)
        # Instead, let's just create a new table manually with desired schema.
        # This mirrors the SQLAlchemy Item definition.
        cursor.execute("""
            CREATE TABLE items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                unit TEXT,
                price REAL DEFAULT 0.0,
                standard_stock REAL DEFAULT 0.0,
                actual_stock REAL DEFAULT 0.0,
                pending_order REAL DEFAULT 0.0,
                requires_refill BOOLEAN DEFAULT 0 NOT NULL,
                supplier_id INTEGER REFERENCES suppliers(id)
            );
        """)
        
        # 3. Copy data from items_old to items
        # Find all columns that exist in items_old
        cursor.execute("PRAGMA table_info(items_old)")
        old_cols = [c[1] for c in cursor.fetchall()]
        
        common_cols = [c for c in ["id", "name", "description", "unit", "price", "standard_stock", "actual_stock", "pending_order", "requires_refill", "supplier_id"] if c in old_cols]
        col_list = ", ".join(common_cols)
        
        cursor.execute(f"INSERT INTO items ({col_list}) SELECT {col_list} FROM items_old;")
        
        # 4. Drop the old table
        cursor.execute("DROP TABLE items_old;")
        
        # Re-create the non-unique index on id if needed (Alchemy will do it via create_all too, but good to be careful)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_items_id ON items (id);")
        
        conn.commit()
        print("Migration complete!")
    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
