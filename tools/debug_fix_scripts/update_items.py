from database import SessionLocal, Item

def update_supply_list():
    new_supplies = [
        ("EPSON 005 INK", ""),
        ("CORRECTION TAPE", "SMALL"),
        ("DOUBLE SIDED TAPE", ""),
        ("DTR", ""),
        ("ENVELOPE (LONG)", "BROWN"),
        ("ENVELOPE (SHORT)", "BROWN"),
        ("EPSON 003 INK", "CYAN"),
        ("EPSON 003 INK", "BLK"),
        ("EPSON 005 INK", "BLK"),
        ("EXPANDED ENVELOPE (LONG)", "RED"),
        ("EXPANDED ENVELOPE (LONG)", "GREEN"),
        ("EXPANDED ENVELOPE (LONG)", "YELLOW"),
        ("EXPANDED FOLDER (LONG)", "RED"),
        ("EXPANDED FOLDER (LONG)", "YELLOW"),
        ("FOLDER (LONG)", "BROWN"),
        ("FOLDER SLIDER", "YELLOW"),
        ("FOLDER SLIDER", "PURPLE"),
        ("FOLDER SLIDER", "BLACK"),
        ("HIGHLIGHTER", ""),
        ("LAMINATING FILM", ""),
        ("LOGBOOK (RECORD BOOK)", "150 PAGES"),
        ("LOGBOOK (RECORD BOOK)", "300 PAGES"),
        ("MARKER", "PERMANENT"),
        ("MARKER", "WHITEBOARD"),
        ("MASKING TAPE", "WHITE"),
        ("PACKAGING TAPE", "TRANSPARENT"),
        ("PAPER CLIP", "BIG"),
        ("PAPER CLIP", "SMALL"),
        ("PAPER FASTENER", "SHORT"),
        ("PAPER FASTENER", "LONG"),
        ("PLASTIC FOLDER", "YELLOW"),
        ("PLASTIC FOLDER", "PURPLE"),
        ("PLASTIC FOLDER", "GREEN"),
        ("PVC CARD", ""),
        ("REFILL INK", "PERMANENT"),
        ("REFILL INK", "WHITEBOARD"),
        ("RUBBER BAND", ""),
        ("SCOTCH TAPE", "SMALL"),
        ("SCOTCH TAPE", "BIG"),
        ("STAMP PAD INK", "BLK"),
        ("STAMP PAD INK", "BLUE"),
        ("STAMP PAD INK", "RED"),
        ("STAPLE WIRE", "MAX"),
        ("STAPLER", "HEAVY DUTY - KANG"),
        ("SUBLIMATION INK", "YELLOW"),
        ("SUBLIMATION INK", "CYAN"),
        ("SUBLIMATION INK", "MAGENTA"),
        ("SUBLIMATION INK", "BLK"),
        ("UV DYE INK", "RED"),
        ("UV DYE INK", "YELLOW"),
        ("UV DYE INK", "CYAN"),
        ("UV DYE INK", "BLACK"),
        ("WHISTLE", ""),
        ("PAPER CUTTER", "METAL"),
        ("BAYGON SPRAY", ""),
        ("SCISSOR", "DRESSMAKING"),
        ("BALLPEN HBII", "BLUE"),
        ("BAIRAN", ""),
        ("CLEARBOOK", "LONG"),
        ("LOGBOOK (RECORD BOOK)", "JR"),
        ("RISO (LEAVE OF ABSENCE)", "SHORT"),
        ("RISO (ATTENDING PHYSICIAN REPORT)", "SHORT"),
        ("RISO (ACCIDENT/ SICKNESS INSURANCE REPORT)", "SHORT"),
        ("RISO (ACCIDENT REPORT)", "SHORT"),
        ("RISO (QUITCLAIM FORM - PAGE 1)", "LONG"),
        ("RISO (QUITCLAIM FORM - PAGE 2)", "LONG")
    ]

    with SessionLocal() as session:
        for name, desc in new_supplies:
            # Check if item with this name AND description already exists
            # Note: The database 'items' table has a unique constraint on 'name'.
            # If the user wants multiple "EPSON 003 INK" with different descriptions, 
            # we need to be careful. Current schema has unique(name). 
            # I will modify the logic to use name + desc in the name field or just update description.
            
            # Since 'name' is unique, I'll combine name and description for the identifier 
            # if multiple exists, or just ensure the description is updated.
            # Looking at the list, items like "EPSON 003 INK" appear twice with different colors.
            
            full_name = f"{name} ({desc})" if desc else name
            
            item = session.query(Item).filter_by(name=full_name).first()
            if not item:
                # Fallback check for exact name match to update description if possible
                item = session.query(Item).filter_by(name=name).first()
                if item and not item.description:
                    item.description = desc
                    item.name = full_name # Standardize to full name
                    print(f"Updated: {full_name}")
                else:
                    item = Item(name=full_name, description=desc)
                    session.add(item)
                    print(f"Added: {full_name}")
            else:
                item.description = desc
                print(f"Exists: {full_name}")
        
        session.commit()
    print("Supply list update complete.")

if __name__ == "__main__":
    update_supply_list()
