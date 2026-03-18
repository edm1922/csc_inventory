
import sqlite3
from database import DB_FILE

def move_items_to_warehouse():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # List of items provided by the user
    warehouse_items_raw = [
        "BALLPEN (Standard)",
        "BALLPEN (BODY)",
        "BALLPEN (BLACK)",
        "BALLPEN CPG",
        "PENTLE PEN",
        "STABILO",
        "HIGHLIGHTER",
        "MARKER (PERMANENT)",
        "PERMANENT INK",
        "WHITEBOARD MARKER",
        "WHITEBOARD (BODY) PENTLE PEN",
        "WHITE BOARD",
        "REFILL / REFIL",
        "REFILL BALLPEN",
        "INK REFILL",
        "INK (WHITE BOARD)",
        "CORRECTION TAPE",
        "LOGBOOK",
        "CLAS RECORD / CLASS RECORD",
        "BROWN FOLDER",
        "CLIPBOARD",
        "CALCULATOR",
        "CUTTER",
        "WHISTLE",
        "EARPLUG / EAR PLUG"
    ]

    try:
        # 1. Get WAREHOUSE ID
        cursor.execute("SELECT id FROM locations WHERE name = 'WAREHOUSE'")
        row = cursor.fetchone()
        if not row:
            print("Error: WAREHOUSE location not found.")
            return
        wh_loc_id = row[0]
        
        # 2. Process each item
        moved_count = 0
        added_count = 0
        
        for item_name in warehouse_items_raw:
            # Try to match existing items (handling some slash variants)
            search_pattern = item_name
            if " / " in item_name:
                parts = item_name.split(" / ")
                # Check for either part
                cursor.execute("SELECT id FROM items WHERE name LIKE ? OR name LIKE ?", (f"%{parts[0]}%", f"%{parts[1]}%"))
            else:
                cursor.execute("SELECT id FROM items WHERE name LIKE ?", (f"%{item_name}%",))
            
            items_found = cursor.fetchall()
            
            if not items_found:
                # If not found, create it as a new item record so it appears in the warehouse list
                cursor.execute("INSERT INTO items (name, requires_refill) VALUES (?, ?)", (item_name.upper(), False))
                item_id = cursor.lastrowid
                cursor.execute("INSERT INTO stocks (item_id, location_id, quantity) VALUES (?, ?, 0.0)", (item_id, wh_loc_id))
                added_count += 1
            else:
                for (item_id,) in items_found:
                    # Check if stock entry already exists for warehouse
                    cursor.execute("SELECT id FROM stocks WHERE item_id = ? AND location_id = ?", (item_id, wh_loc_id))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO stocks (item_id, location_id, quantity) VALUES (?, ?, 0.0)", (item_id, wh_loc_id))
                        moved_count += 1

        conn.commit()
        print(f"Inventory Update Complete:")
        print(f"- {moved_count} existing items linked to WAREHOUSE.")
        print(f"- {added_count} new items created and linked to WAREHOUSE.")
        
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    move_items_to_warehouse()
