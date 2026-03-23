import pandas as pd
from datetime import datetime
from database import SessionLocal, Employee, Department, Item, SupplyRequest, RequestItem

EXCEL_FILE = "REQUEST SUPPLIES.xlsx"

def clean_and_import_sheet(db_session, sheet_name):
    # 1. Load the Excel file completely raw to find the actual header row
    try:
        raw_df = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name, header=None)
    except Exception as e:
        print(f"Error reading sheet {sheet_name}: {e}")
        return

    if raw_df.empty:
        return

    # Find the row that contains 'SUPPLIES'
    header_row_idx = -1
    for idx, row in raw_df.iterrows():
        if row.astype(str).str.contains('SUPPLIES').any():
            header_row_idx = idx
            break
            
    if header_row_idx == -1:
        print(f"Sheet {sheet_name} does not match expected Request Form format. Skipping.")
        return

    # Read the data properly now that we know where the header is
    df = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name, header=header_row_idx)


    # Keep only rows where 'SUPPLIES' is not null
    df = df.dropna(subset=['SUPPLIES'])

    # 2. Extract metadata from the TOP of the sheet (Rows 0-4)
    # We load the sheet again without skipping to grab metadata
    df_meta = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name, nrows=5)
    
    # Safely extract Area, Shift, Date, Supervisor
    try:
        # Date is usually in Row 1, Column 2 (using 0-indexing)
        raw_date = df_meta.iloc[1, 2]
        if pd.isna(raw_date):
            req_date = datetime.utcnow()
        else:
            req_date = pd.to_datetime(raw_date)

        # Shift is usually in Row 2, Column 2
        raw_shift = df_meta.iloc[2, 2]
        shift_val = str(raw_shift) if pd.notna(raw_shift) else "Unknown"

        # Area is usually in Row 3, Column 2
        raw_area = df_meta.iloc[3, 2]
        area_val = str(raw_area) if pd.notna(raw_area) else "Unknown"
        
        # Supervisor is usually in Row 4, Column 2
        raw_super = df_meta.iloc[4, 2]
        super_val = str(raw_super).replace("SUPER VISOR: ", "").strip() if pd.notna(raw_super) else "Unknown"

    except IndexError:
        print(f"Failed to read metadata for {sheet_name}. Using defaults.")
        req_date, shift_val, area_val, super_val = datetime.utcnow(), "Unknown", "Unknown", "Unknown"

    # --- SAVE DEPARTMENT ---
    department = db_session.query(Department).filter_by(area_name=area_val, shift=shift_val).first()
    if not department:
        department = Department(area_name=area_val, shift=shift_val, supervisor=super_val)
        db_session.add(department)
        db_session.flush() # Get the ID immediately
        
    # Variables to track current person so blank spaces inherit the last person
    current_recipient = None
    current_scope = None

    # Track distinct requests for this batch (grouped by Employee/Recipient)
    # Mapping constraint: 1 Request per Employee per Date/Shift
    request_map = {}

    # 3. Iterate through valid item rows
    for index, row in df.iterrows():
        # Clean Recipient
        recipient_val = row.get('RECIPIENT')
        if pd.notna(recipient_val) and str(recipient_val).strip() != "":
            current_recipient = str(recipient_val).strip()
            
        scope_val = row.get('SCOPE OF WORK')
        if pd.notna(scope_val) and str(scope_val).strip() != "":
            current_scope = str(scope_val).strip()

        # If we still don't have a recipient after scanning down, skip this row
        if not current_recipient:
            continue

        # --- SAVE EMPLOYEE ---
        employee = db_session.query(Employee).filter_by(name=current_recipient).first()
        if not employee:
            employee = Employee(name=current_recipient, role=current_scope)
            db_session.add(employee)
            db_session.flush()

        # --- SETUP REQUEST (Header) ---
        if employee.id not in request_map:
            new_request = SupplyRequest(
                request_date=req_date,
                employee_id=employee.id,
                department_id=department.id
            )
            db_session.add(new_request)
            db_session.flush()
            request_map[employee.id] = new_request

        active_request = request_map[employee.id]

        # --- IDENTIFY ITEM ---
        raw_supply = str(row['SUPPLIES']).strip().upper()
        item_name_clean = raw_supply
        
        inventory_item = db_session.query(Item).filter_by(name=item_name_clean).first()
        if not inventory_item:
            inventory_item = Item(name=item_name_clean)
            db_session.add(inventory_item)
            db_session.flush()


        # Clean Quantity (Default to 1 if blank, handle misspelled column header)
        qty_col = 'QUANTITY' if 'QUANTITY' in df.columns else 'QUANITY'
        raw_qty = row.get(qty_col)
        
        try:
            # Handle text like "1 BOT" -> extract numbers
            if pd.isna(raw_qty):
                req_qty = 1.0
            else:
                qty_str = "".join([c for c in str(raw_qty) if c.isdigit() or c == '.'])
                req_qty = float(qty_str) if qty_str else 1.0
        except Exception:
            req_qty = 1.0
            
        # Clean frequency
        freq_val = row.get('FREQUENCY')
        freq_str = str(freq_val) if pd.notna(freq_val) else None

        # --- ADD REQUEST ITEM ---
        req_item = RequestItem(
            request_id=active_request.id,
            item_id=inventory_item.id,
            quantity=req_qty,
            frequency=freq_str
        )
        db_session.add(req_item)
        
    db_session.commit()
    print(f"Successfully processed and imported sheet: {sheet_name}")


def run_full_import():
    xl = pd.ExcelFile(EXCEL_FILE)
    print(f"Found sheets: {xl.sheet_names}")
    
    with SessionLocal() as db_session:
        for sheet in xl.sheet_names:
            print(f"Processing {sheet}...")
            clean_and_import_sheet(db_session, sheet)

if __name__ == "__main__":
    run_full_import()
