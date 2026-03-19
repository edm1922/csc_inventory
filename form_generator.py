import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
import os

FORM_FILENAME = "BLANK_REQUEST_FORM.xlsx"

def generate_blank_form():
    """Generates a perfectly formatted, printable blank Excel form for supply requests."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Supply Request Form"

    # Define common styles
    bold_font = Font(bold=True)
    header_font = Font(bold=True, size=14, color="FFFFFF")
    title_font = Font(bold=True, size=18)
    
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")

    # Column Widths
    ws.column_dimensions['A'].width = 5   # "#"
    ws.column_dimensions['B'].width = 35  # "Item Name"
    ws.column_dimensions['C'].width = 12  # "Quantity"
    ws.column_dimensions['D'].width = 15  # "Is Refill? (Y/N)"
    ws.column_dimensions['E'].width = 25  # "Frequency / Remarks"

    # Company Name Header
    ws.merge_cells('B1:E1')
    ws['B1'] = "CENTRO SERVICES COOPERATIVE"
    ws['B1'].font = Font(bold=True, size=24, color="1F497D") # Dark Blue
    ws['B1'].alignment = center_align

    # Form Title
    ws.merge_cells('B2:E2')
    ws['B2'] = "MATERIAL / SUPPLY REQUEST FORM"
    ws['B2'].font = title_font
    ws['B2'].alignment = center_align

    # Employee / Department Block (Top)
    metadata_labels = [
        ("B3", "Date:"), ("D3", "Shift:"),
        ("B4", "Employee Name:"), ("D4", "Employee Role:"),
        ("B5", "Department Area:"), ("D5", "Supervisor:")
    ]
    
    for cell_loc, label in metadata_labels:
        ws[cell_loc] = label
        ws[cell_loc].font = bold_font
        ws[cell_loc].alignment = left_align
        
        # Create a line to write on next to the label
        blank_cell = f"{chr(ord(cell_loc[0]) + 1)}{cell_loc[1]}"
        ws[blank_cell].border = Border(bottom=Side(style='thin'))

    # Table Headers (Row 8)
    headers = ["#", "Item Requested", "Quantity", "Is Refill? (Y/N)", "Frequency / Remarks"]
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=8, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.alignment = center_align
        cell.fill = header_fill
        cell.border = thin_border

    # Blank Rows for filling (Rows 9 to 25)
    for row_num in range(9, 26):
        # Auto-number the # column
        num_cell = ws.cell(row=row_num, column=1)
        num_cell.value = row_num - 8
        num_cell.alignment = center_align
        num_cell.border = thin_border
        
        # Add borders to blank cells
        for col_num in range(2, 6):
            cell = ws.cell(row=row_num, column=col_num)
            cell.border = thin_border

    # Signatures block at the bottom
    ws['B28'] = "Requested By:"
    ws['B28'].font = bold_font
    ws['C28'].border = Border(bottom=Side(style='thin'))
    ws.merge_cells('C28:E28')
    
    ws['B30'] = "Approved By:"
    ws['B30'].font = bold_font
    ws['C30'].border = Border(bottom=Side(style='thin'))
    ws.merge_cells('C30:E30')

    # Page Setup for Printing
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    
    # Set print margins
    ws.page_margins.left = 0.5
    ws.page_margins.right = 0.5
    ws.page_margins.top = 0.75
    ws.page_margins.bottom = 0.75

    # Save the form
    wb.save(FORM_FILENAME)
    print(f"Printable form generated at: {os.path.abspath(FORM_FILENAME)}")

def generate_populated_report(employee_name, role, area, shift, supervisor, requests_data):
    """Generates a populated supply request history report for a specific employee."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Request History"

    # Define common styles
    bold_font = Font(bold=True)
    header_font = Font(bold=True, size=14, color="FFFFFF")
    title_font = Font(bold=True, size=18)
    
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")

    # Column Widths
    ws.column_dimensions['A'].width = 15  # "Date"
    ws.column_dimensions['B'].width = 30  # "Item Requested"
    ws.column_dimensions['C'].width = 12  # "Quantity"
    ws.column_dimensions['D'].width = 15  # "Is Refill?"
    ws.column_dimensions['E'].width = 25  # "Frequency"

    # Company Name Header
    ws.merge_cells('A1:E1')
    ws['A1'] = "CENTRO SERVICES COOPERATIVE"
    ws['A1'].font = Font(bold=True, size=24, color="1F497D")
    ws['A1'].alignment = center_align

    # Form Title
    ws.merge_cells('A2:E2')
    ws['A2'] = f"SUPPLY REQUEST HISTORY: {employee_name}"
    ws['A2'].font = title_font
    ws['A2'].alignment = center_align

    # Metadata Block
    ws['A4'] = "Employee Name:"; ws['B4'] = employee_name
    ws['A5'] = "Employee Role:"; ws['B5'] = role
    ws['A6'] = "Shift:";         ws['B6'] = shift
    ws['D4'] = "Area:";          ws['E4'] = area
    ws['D5'] = "Supervisor:";    ws['E5'] = supervisor or "N/A"

    for row in range(4, 7):
        for col in [1, 4]:
            ws.cell(row=row, column=col).font = bold_font

    # Table Headers (Row 8)
    headers = ["Date", "Item Requested", "Quantity", "Is Refill?", "Frequency / Remarks"]
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=8, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.alignment = center_align
        cell.fill = header_fill
        cell.border = thin_border

    # Populating Data
    for row_idx, data in enumerate(requests_data, 9):
        # data is expected to be (date_str, item_name, qty, refill_str, frequency)
        for col_idx, value in enumerate(data, 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.value = value
            cell.border = thin_border
            cell.alignment = left_align if col_idx == 2 else center_align

    # Page Setup
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToPage = True
    
    filename = f"HISTORY_{employee_name.replace(' ', '_').replace(',', '')}.xlsx"
    wb.save(filename)
    return filename

def generate_consumption_report(data_rows):
    """Generates a summary Excel report for the Consumption & Usage Analysis."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Consumption Analysis"

    # Common Styles
    bold_font = Font(bold=True)
    header_font = Font(bold=True, size=12, color="FFFFFF")
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")

    # Column Widths
    ws.column_dimensions['A'].width = 30  # Employee
    ws.column_dimensions['B'].width = 25  # Item
    ws.column_dimensions['C'].width = 15  # Total Requests
    ws.column_dimensions['D'].width = 18  # Avg Days Between
    ws.column_dimensions['E'].width = 18  # Weekly Usage
    ws.column_dimensions['F'].width = 18  # Yearly Usage
    ws.column_dimensions['G'].width = 20  # Status

    # Company Header
    ws.merge_cells('A1:G1')
    ws['A1'] = "CENTRO SERVICES COOPERATIVE - SUPPLY CONSUMPTION ANALYSIS"
    ws['A1'].font = Font(bold=True, size=16)
    ws['A1'].alignment = center_align

    # Table Headers
    headers = ["Employee", "Item", "Total Requests", "Avg Days Between", "Weekly Usage", "Yearly Usage", "Status"]
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.alignment = center_align
        cell.fill = header_fill
        cell.border = thin_border

    # Populating Data
    for row_idx, data in enumerate(data_rows, 4):
        for col_idx, value in enumerate(data, 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.value = value
            cell.border = thin_border
            cell.alignment = left_align if col_idx <= 2 else center_align

    filename = "CONSUMPTION_REPORT.xlsx"
    wb.save(filename)
    return filename

def generate_purchase_request_excel(pr_id):
    """Generates a professional Excel Purchase Request form in Portrait orientation with thick borders."""
    from database import SessionLocal, PurchaseRequest, PurchaseItem
    from sqlalchemy.orm import joinedload
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from datetime import datetime
    import os

    with SessionLocal() as session:
        pr = session.query(PurchaseRequest).options(joinedload(PurchaseRequest.items)).get(pr_id)
        if not pr:
            raise ValueError("PR not found.")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "PURCHASE REQUEST"

        # Define styles
        bold_font = Font(bold=True)
        title_font = Font(bold=True, size=18)
        company_font = Font(bold=True, size=14)
        pr_no_label_font = Font(bold=True, color="C00000") # Red
        
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_align = Alignment(horizontal="left", vertical="center")
        right_align = Alignment(horizontal="right", vertical="center")
        
        # THICKER BORDERS - using medium thickness
        thick_border = Border(
            left=Side(style='medium'), right=Side(style='medium'),
            top=Side(style='medium'), bottom=Side(style='medium')
        )
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        bottom_border = Border(bottom=Side(style='thin'))

        # Set Column Widths for Portrait - Balanced for 3 signature columns
        ws.column_dimensions['A'].width = 34  # Item Description
        ws.column_dimensions['B'].width = 12  # Purpose / Reason
        ws.column_dimensions['C'].width = 12  # For (Department/End-User)
        ws.column_dimensions['D'].width = 10  # Price
        ws.column_dimensions['E'].width = 10  # QTY
        ws.column_dimensions['F'].width = 10  # Unit
        ws.column_dimensions['G'].width = 14  # Total

        # Row heights
        ws.row_dimensions[1].height = 25
        ws.row_dimensions[2].height = 25
        ws.row_dimensions[9].height = 35  # Header row

        # Header Section
        ws.merge_cells('A1:G1')
        ws['A1'] = "CENTRO SERVICES COOPERATIVE"
        ws['A1'].font = company_font
        ws['A1'].alignment = center_align

        ws.merge_cells('A2:G2')
        ws['A2'] = "PURCHASE REQUEST FORM"
        ws['A2'].font = title_font
        ws['A2'].alignment = center_align

        # Metadata Section
        # Row 3 - Date and PR No.
        ws['A3'] = "Date:"
        ws['A3'].font = bold_font
        ws.merge_cells('B3:C3')
        ws['B3'] = pr.request_date.strftime("%m/%d/%Y")
        ws['B3'].border = bottom_border
        
        ws['D3'] = "PR No.:"
        ws['D3'].font = pr_no_label_font
        ws['D3'].alignment = right_align
        ws.merge_cells('E3:G3')
        ws['E3'] = pr.pr_no
        ws['E3'].font = bold_font
        ws['E3'].border = bottom_border
        
        # Row 4 - Department
        ws['A4'] = "Department:"
        ws['A4'].font = bold_font
        ws.merge_cells('B4:G4')
        ws['B4'] = pr.department
        ws['B4'].border = bottom_border
        
        # Row 5 - End-User
        ws['A5'] = "End-User / Person Who Will Use:"
        ws['A5'].font = bold_font
        ws.merge_cells('B5:G5')
        ws['B5'] = pr.end_user or ""
        ws['B5'].border = bottom_border
        
        # Row 6 - Position
        ws['A6'] = "Position:"
        ws['A6'].font = bold_font
        ws.merge_cells('B6:G6')
        ws['B6'] = pr.position or ""
        ws['B6'].border = bottom_border

        # Item Details Row
        ws.merge_cells('A8:G8')
        ws['A8'] = "ITEM DETAILS"
        ws['A8'].font = bold_font

        # Table Headers with THICK BORDERS
        headers = ["Item Description", "Purpose / Reason", "For (Department / End-User)", "Price", "QTY", "Unit", "Total"]
        columns = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
        for col, header in zip(columns, headers):
            cell = ws[f'{col}9']
            cell.value = header
            cell.font = bold_font
            cell.alignment = center_align
            cell.border = thick_border
            cell.fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

        # Table Content
        current_row = 10
        total_sum = 0.0
        for item in pr.items:
            for col_idx, val in enumerate([item.description, item.purpose, item.for_dept, item.price, item.qty, item.unit, item.total], 1):
                cell = ws.cell(row=current_row, column=col_idx, value=val)
                cell.border = thick_border
                
                if col_idx == 1: cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                elif col_idx == 2: cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                elif col_idx == 3: cell.alignment = Alignment(horizontal="left", vertical="center")
                elif col_idx == 4: 
                    cell.alignment = right_align
                    cell.number_format = '#,##0.00'
                elif col_idx == 5: cell.alignment = center_align
                elif col_idx == 6: cell.alignment = center_align
                elif col_idx == 7: 
                    cell.alignment = right_align
                    cell.number_format = '#,##0.00'
            total_sum += item.total
            current_row += 1

        # Total Line
        ws.merge_cells(f'A{current_row+1}:E{current_row+1}')
        ws[f'A{current_row+1}'] = "Estimated Total:"
        ws[f'A{current_row+1}'].font = bold_font
        ws[f'A{current_row+1}'].alignment = left_align
        
        ws[f'F{current_row+1}'] = "Php."
        ws[f'F{current_row+1}'].font = bold_font
        ws[f'F{current_row+1}'].alignment = right_align
        
        ws[f'G{current_row+1}'] = total_sum
        ws[f'G{current_row+1}'].font = bold_font
        ws[f'G{current_row+1}'].alignment = right_align
        ws[f'G{current_row+1}'].number_format = '#,##0.00'

        # Signature Section - Balanced into 3 equal widths (Col A, B-D, E-G)
        sig_row = current_row + 3
        # Headers
        ws[f'A{sig_row}'] = "Requested By:"
        ws[f'A{sig_row}'].font = bold_font
        ws[f'A{sig_row}'].alignment = center_align
        
        ws.merge_cells(f'B{sig_row}:D{sig_row}')
        ws[f'B{sig_row}'] = "Prepared By:"
        ws[f'B{sig_row}'].font = bold_font
        ws[f'B{sig_row}'].alignment = center_align
        
        ws.merge_cells(f'E{sig_row}:G{sig_row}')
        ws[f'E{sig_row}'] = "Approved By:"
        ws[f'E{sig_row}'].font = bold_font
        ws[f'E{sig_row}'].alignment = center_align
        
        # Names
        ws[f'A{sig_row+1}'] = "" # Space for signature/name
        ws[f'A{sig_row+1}'].alignment = center_align
        
        ws.merge_cells(f'B{sig_row+1}:D{sig_row+1}')
        ws[f'B{sig_row+1}'] = pr.prepared_by or ""
        ws[f'B{sig_row+1}'].alignment = center_align
        
        ws.merge_cells(f'E{sig_row+1}:G{sig_row+1}')
        ws[f'E{sig_row+1}'] = pr.approved_by or ""
        ws[f'E{sig_row+1}'].alignment = center_align
        
        # (Signature underlines removed)
        
        # (Labels row removed per user request)

        # Page Setup
        ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        
        ws.page_margins.left = 0.3
        ws.page_margins.right = 0.3
        ws.page_margins.top = 0.5
        ws.page_margins.bottom = 0.5
        
        ws.print_options.horizontalCentered = True
        ws.print_title_rows = '1:9'
        
        ws.print_area = f"A1:G{sig_row+1}"

        filename = f"PURCHASE_REQUEST_{pr.pr_no}.xlsx"
        wb.save(filename)
        return filename

if __name__ == "__main__":
    generate_blank_form()
