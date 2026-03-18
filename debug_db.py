import sqlite3
import os

DB_FILE = "supply_system.db"

def check_db():
    if not os.path.exists(DB_FILE):
        print(f"Error: Database {DB_FILE} not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        # Check locations
        print("--- LOCATIONS ---")
        cursor.execute("SELECT id, name FROM locations")
        for row in cursor.fetchall():
            print(row)
            
        # Check source/dest of CAN LABELLING WAREHOUSE requests
        print("\n--- 'CAN LABELLING WAREHOUSE' REQUESTS ---")
        query = """
            SELECT r.id, d.area_name, l_src.name, l_dst.name, r.source_location_id, r.dest_location_id
            FROM supply_requests r 
            JOIN departments d ON r.department_id = d.id 
            LEFT JOIN locations l_src ON r.source_location_id = l_src.id 
            LEFT JOIN locations l_dst ON r.dest_location_id = l_dst.id
            WHERE d.area_name LIKE '%CAN LABELLING%'
            LIMIT 20
        """
        cursor.execute(query)
        for row in cursor.fetchall():
            print(row)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_db()
