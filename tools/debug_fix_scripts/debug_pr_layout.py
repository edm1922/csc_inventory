import openpyxl
wb = openpyxl.load_workbook('PURCHASE.xlsx', data_only=True)
ws = wb['PR FORM']

with open('layout_inspection.txt', 'w') as f:
    f.write("--- Column Widths ---\n")
    for col in ws.column_dimensions:
        f.write(f"Col {col}: {ws.column_dimensions[col].width}\n")

    f.write("\n--- Cell Values (Rows 1-40) ---\n")
    for r_idx in range(1, 41):
        row_data = []
        for c_idx in range(1, 15): # A-O
            val = ws.cell(row=r_idx, column=c_idx).value
            row_data.append(str(val) if val is not None else ".")
        f.write(f"R{r_idx:2}: {' | '.join(row_data)}\n")
