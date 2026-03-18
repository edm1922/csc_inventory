
import sqlite3
from database import DB_FILE

def consolidate_to_main_office():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        # 1. Get MAIN OFFICE ID
        cursor.execute("SELECT id FROM locations WHERE name = 'MAIN OFFICE'")
        row = cursor.fetchone()
        if not row:
            print("Error: MAIN OFFICE location not found.")
            return
        main_loc_id = row[0]
        
        # 2. Get all Items
        cursor.execute("SELECT id FROM items")
        items = cursor.fetchall()
        
        for (item_id,) in items:
            # Check if there is already a stock entry for MAIN OFFICE
            cursor.execute("SELECT id, quantity FROM stocks WHERE item_id = ? AND location_id = ?", (item_id, main_loc_id))
            main_stock_row = cursor.fetchone()
            
            # Sum up all stock for this item across ALL locations to consolidate it
            cursor.execute("SELECT SUM(quantity) FROM stocks WHERE item_id = ?", (item_id,))
            total_stock = cursor.fetchone()[0] or 0.0
            
            if main_stock_row:
                # Update existing main office stock with the total consolidated amount
                cursor.execute("UPDATE stocks SET quantity = ? WHERE id = ?", (total_stock, main_stock_row[0]))
            else:
                # Create new main office stock entry
                cursor.execute("INSERT INTO stocks (item_id, location_id, quantity) VALUES (?, ?, ?)", (item_id, main_loc_id, total_stock))
            
            # 3. Zero out or remove stock from other locations for this item
            cursor.execute("DELETE FROM stocks WHERE item_id = ? AND location_id != ?", (item_id, main_loc_id))
            
        conn.commit()
        print(f"Successfully consolidated all supplies for {len(items)} items into MAIN OFFICE storage.")
        
    except Exception as e:
        conn.rollback()
        print(f"Error during consolidation: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    consolidate_to_main_office()
