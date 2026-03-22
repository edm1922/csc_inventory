import sqlite3

def run():
    conn = sqlite3.connect("supply_system.db")
    cursor = conn.cursor()
    
    # Check current table schema
    cursor.execute("PRAGMA table_info(items)")
    print("Columns:", cursor.fetchall())
    
    # Check indices
    cursor.execute("PRAGMA index_list(items)")
    indices = cursor.fetchall()
    print("Indices:", indices)
    
    # If there's a unique index, try to drop it.
    # SQLite often creates a unique index automatically for 'unique=True'.
    # Note: SQLite does not allow dropping 'sqlite_autoindex_items_1'
    # The only way is to recreate the table.
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    run()
