import pandas as pd
from sqlalchemy.orm import joinedload
from database import SessionLocal, SupplyRequest, RequestItem

EXPORT_FILE = "CLEANED_SUPPLY_INVENTORY.xlsx"

def export_to_excel(start_date=None, end_date=None, area=None, shift=None, only_pending=False):
    from datetime import datetime
    from database import parse_frequency, Department
    
    with SessionLocal() as session:
        # 1. Base query for all relevant request items
        query = session.query(RequestItem).options(
            joinedload(RequestItem.item),
            joinedload(RequestItem.supply_request).joinedload(SupplyRequest.employee),
            joinedload(RequestItem.supply_request).joinedload(SupplyRequest.department)
        ).join(SupplyRequest).join(Department)

        # 2. Sequential filters
        if start_date:
            query = query.filter(SupplyRequest.request_date >= start_date)
        if end_date:
            query = query.filter(SupplyRequest.request_date <= end_date)
        if area:
            query = query.filter(Department.area_name == area)
        if shift:
            query = query.filter(Department.shift == shift)

        all_results = query.all()

        if not all_results:
            print("No data found matching filters.")
            return None

        # Flatten the relational data into a list of dictionaries
        data = []
        now = datetime.now()
        
        for req in all_results:
            is_late = req.supply_request.status == "PENDING"
            status = "🔴 PENDING/LATE" if is_late else "🟢 OK"
            
            if only_pending and not is_late:
                continue

            row = {
                "Status": status,
                "Request Date": req.supply_request.request_date.strftime("%Y-%m-%d"),
                "Employee Name": req.supply_request.employee.name,
                "Employee Role": req.supply_request.employee.role,
                "Department Area": req.supply_request.department.area_name,
                "Shift": req.supply_request.department.shift,
                "Supervisor": req.supply_request.department.supervisor,
                "Item Requested": req.item.name,
                "Quantity": req.quantity,
                "Is Refill?": "Yes" if req.is_refill_request else "No",
                "Frequency": req.frequency or "N/A"
            }
            data.append(row)

        if not data:
            return None

        df = pd.DataFrame(data)
        
        filename = f"FILTERED_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="Supply Report", index=False)
            worksheet = writer.sheets["Supply Report"]
            for idx, col in enumerate(df):
                series = df[col]
                max_len = max(series.astype(str).map(len).max(), len(str(series.name))) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = max_len

        return filename

def generate_inventory_checklist(data_rows, location_name="ALL"):
    """
    Generates a professional Excel checklist for inventory.
    data_rows: List of dicts with keys ['Item', 'Standard', 'Price', 'Actual']
    """
    from datetime import datetime
    import pandas as pd
    
    df = pd.DataFrame(data_rows)
    # Ensure correct column order
    cols = ["Item", "Standard", "Price", "Actual"]
    df = df[cols]
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"INVENTORY_CHECKLIST_{location_name}_{timestamp}.xlsx"
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Checklist", index=False)
        worksheet = writer.sheets["Checklist"]
        
        # Style header and columns
        for idx, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 4
            worksheet.column_dimensions[chr(65 + idx)].width = max_len
            
    return filename

if __name__ == "__main__":
    export_to_excel()
