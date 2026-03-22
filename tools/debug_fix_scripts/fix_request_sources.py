import sqlite3
import os

DB_FILE = "supply_system.db"

def fix_locations():
    if not os.path.exists(DB_FILE):
        print(f"Error: Database {DB_FILE} not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        # 1. Get Location IDs
        cursor.execute("SELECT id FROM locations WHERE name = 'MAIN OFFICE'")
        main_id = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM locations WHERE name = 'WAREHOUSE'")
        warehouse_id = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM locations WHERE name = 'SATELLITE OFFICE'")
        sat_id_row = cursor.fetchone()
        
        if not sat_id_row:
            # Re-seed if missing
            print("SATELLITE OFFICE missing, re-adding...")
            cursor.execute("INSERT INTO locations (name) VALUES ('SATELLITE OFFICE')")
            conn.commit()
            cursor.execute("SELECT id FROM locations WHERE name = 'SATELLITE OFFICE'")
            sat_id = cursor.fetchone()[0]
        else:
            sat_id = sat_id_row[0]
            
        print(f"MAIN OFFICE ID: {main_id}")
        print(f"WAREHOUSE ID: {warehouse_id}")
        print(f"SATELLITE OFFICE ID: {sat_id}")

        # Let's get all departments
        cursor.execute("SELECT id, area_name FROM departments")
        departments = cursor.fetchall()
        
        main_office_keywords = ['HR', 'ACCOUNTING', 'ADMIN', 'MANAGEMENT', 'OFFICE']
        
        updated_count = 0
        for dept_id, area_name in departments:
            area_upper = (area_name or "").upper()
            is_main_office_dept = any(kw in area_upper for kw in main_office_keywords)
            
            if not is_main_office_dept:
                # Factory workers: Source from Warehouse, Live in Satellite Office
                cursor.execute(
                    "UPDATE supply_requests SET source_location_id = ?, dest_location_id = ? WHERE department_id = ?",
                    (warehouse_id, sat_id, dept_id)
                )
                updated_count += cursor.rowcount
            else:
                # Main Office workers: Source from Main Office, Live in Main Office
                cursor.execute(
                    "UPDATE supply_requests SET source_location_id = ?, dest_location_id = ? WHERE department_id = ?",
                    (main_id, main_id, dept_id)
                )
                updated_count += cursor.rowcount
        
        conn.commit()
        print(f"Successfully updated {updated_count} historical supply requests with correct Locations.")
        
    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_locations()
