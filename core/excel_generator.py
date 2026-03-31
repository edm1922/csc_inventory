import pandas as pd
import os
from openpyxl.styles import Font, PatternFill, Alignment

def generate_excel_report(report_title, table_headers, table_data, filename="report.xlsx"):
    """
    Generates a stylized Excel report from table headers and data.
    """
    df = pd.DataFrame(table_data, columns=table_headers)
    
    # Use ExcelWriter for styling
    writer = pd.ExcelWriter(filename, engine='openpyxl')
    df.to_excel(writer, index=False, sheet_name='Report')
    
    workbook = writer.book
    worksheet = writer.sheets['Report']
    
    # Basic Styling
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2980B9", end_color="2980B9", fill_type="solid")
    
    for cell in worksheet[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        
    # Column width adjustment
    for column_cells in worksheet.columns:
        length = max(len(str(cell.value)) for cell in column_cells)
        worksheet.column_dimensions[column_cells[0].column_letter].width = length + 5
        
    writer.close()
    return os.path.abspath(filename)
