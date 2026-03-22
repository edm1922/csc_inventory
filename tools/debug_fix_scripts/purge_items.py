from database import SessionLocal, Item, RequestItem, SupplyRequest
import re

def cleanup_supplies():
    # User's approved list of BASE names
    approved_base_names = [
        "EPSON 005 INK",
        "CORRECTION TAPE",
        "DOUBLE SIDED TAPE",
        "DTR",
        "ENVELOPE (LONG)",
        "ENVELOPE (SHORT)",
        "EPSON 003 INK",
        "EXPANDED ENVELOPE (LONG)",
        "EXPANDED FOLDER (LONG)",
        "FOLDER (LONG)",
        "FOLDER SLIDER",
        "HIGHLIGHTER",
        "LAMINATING FILM",
        "LOGBOOK (RECORD BOOK)",
        "MARKER",
        "MASKING TAPE",
        "PACKAGING TAPE",
        "PAPER CLIP",
        "PAPER FASTENER",
        "PLASTIC FOLDER",
        "PVC CARD",
        "REFILL INK",
        "RUBBER BAND",
        "SCOTCH TAPE",
        "STAMP PAD INK",
        "STAPLE WIRE",
        "STAPLER",
        "SUBLIMATION INK",
        "UV DYE INK",
        "WHISTLE",
        "PAPER CUTTER",
        "BAYGON SPRAY",
        "SCISSOR",
        "BALLPEN HBW",
        "BAIRAN",
        "CLEARBOOK",
        "RISO (LEAVE OF ABSENCE)",
        "RISO (ATTENDING PHYSICIAN REPORT)",
        "RISO (ACCIDENT/ SICKNESS INSURANCE REPORT)",
        "RISO (ACCIDENT REPORT)",
        "RISO (QUITCLAIM FORM- PAGE 1)",
        "RISO (QUITCLAIM FORM- PAGE 2)",
        "LAGARAW",
        "HOSE",
        "FLOWER CUTTER",
        "COLORED PAPER (LONG)",
        "MONITOR"
    ]
    
    approved_set = {n.strip().upper() for n in approved_base_names}

    with SessionLocal() as session:
        # 1. IDENTIFY ITEMS NOT IN LIST
        items = session.query(Item).all()
        to_delete = []
        
        for item in items:
            base_name = re.sub(r"\s*\(.*?\)$", "", item.name).strip().upper()
            base_name_clean = base_name.replace("FORM- PAGE", "FORM - PAGE")
            
            is_approved = False
            for approved in approved_set:
                approved_clean = approved.replace("FORM- PAGE", "FORM - PAGE")
                if base_name == approved or base_name_clean == approved_clean:
                    is_approved = True
                    break
            
            if not is_approved:
                # Special handle for BALLPEN HBII -> BALLPEN HBW transition
                if "BALLPEN HBII" in base_name:
                    item.name = "BALLPEN HBW"
                    print(f"Renamed: {item.name}")
                    continue
                to_delete.append(item)

        # 2. DELETE HISTORY FIRST
        deleted_history_count = 0
        deleted_item_count = 0
        
        for item in to_delete:
            # Find and delete all request_items linking to this item
            req_items = session.query(RequestItem).filter_by(item_id=item.id).all()
            for ri in req_items:
                req_id = ri.request_id
                session.delete(ri)
                deleted_history_count += 1
                
                # Check if the parent SupplyRequest is now empty
                remaining = session.query(RequestItem).filter(RequestItem.request_id == req_id, RequestItem.id != ri.id).count()
                if remaining == 0:
                    sr = session.query(SupplyRequest).get(req_id)
                    if sr: session.delete(sr)
            
            print(f"Purging item: {item.name}")
            session.delete(item)
            deleted_item_count += 1
        
        # 3. ADD MISSING ITEMS
        for name in approved_base_names:
            normalized_name = name.strip().upper()
            exists = False
            for db_item in session.query(Item).all():
                db_base = re.sub(r"\s*\(.*?\)$", "", db_item.name).strip().upper()
                if db_base == normalized_name or db_base.replace("FORM- PAGE", "FORM - PAGE") == normalized_name.replace("FORM- PAGE", "FORM - PAGE"):
                    exists = True
                    break
            
            if not exists:
                new_item = Item(name=normalized_name)
                session.add(new_item)
                print(f"Added missing item: {normalized_name}")

        session.commit()
    print(f"Cleanup complete. Deleted {deleted_item_count} items and {deleted_history_count} history records.")

if __name__ == "__main__":
    cleanup_supplies()
