
import sqlite3
from database import DB_FILE

def remove_satellite_location():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        # 1. Get IDs
        cursor.execute("SELECT id FROM locations WHERE name = 'SATELLITE OFFICE'")
        row = cursor.fetchone()
        if not row:
            print("SATELLITE OFFICE not found, nothing to do.")
            return
        sat_id = row[0]
        
        cursor.execute("SELECT id FROM locations WHERE name = 'MAIN OFFICE'")
        main_id = cursor.fetchone()[0]
        
        # 2. Reassign Supply Requests
        cursor.execute("UPDATE supply_requests SET source_location_id = ? WHERE source_location_id = ?", (main_id, sat_id))
        cursor.execute("UPDATE supply_requests SET dest_location_id = ? WHERE dest_location_id = ?", (main_id, sat_id))
        
        # 3. Reassign/Remove Stocks
        # If there's stock in Satellite, we should probably move it to Main Office or delete it.
        # Moving it is safer.
        cursor.execute("SELECT item_id, quantity FROM stocks WHERE location_id = ?", (sat_id,))
        sat_stocks = cursor.fetchall()
        for item_id, qty in sat_stocks:
            cursor.execute("SELECT id, quantity FROM stocks WHERE item_id = ? AND location_id = ?", (item_id, main_id))
            main_stock = cursor.fetchone()
            if main_stock:
                cursor.execute("UPDATE stocks SET quantity = quantity + ? WHERE id = ?", (qty, main_stock[0]))
            else:
                cursor.execute("INSERT INTO stocks (item_id, location_id, quantity) VALUES (?, ?, ?)", (item_id, main_id, qty))
        
        cursor.execute("DELETE FROM stocks WHERE location_id = ?", (sat_id,))
        
        # 4. Final Delete
        cursor.execute("DELETE FROM locations WHERE id = ?", (sat_id,))
        
        conn.commit()
        print("Successfully removed SATELLITE OFFICE and reassigned all related data to MAIN OFFICE.")
        
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    remove_satellite_location()
