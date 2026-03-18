import pandas as pd
excel_file = "REQUEST SUPPLIES.xlsx"
df = pd.read_excel(excel_file, sheet_name="MONITORING ", header=None)

print("Rows 0-50 context (Col 0, 1, 4):")
# Col 1: SUPPLIES, Col 4: RECIPIENT
for i in range(50):
    row_data = df.iloc[i].tolist()
    # Only print rows that have some value to save space
    if any(pd.notna(x) for x in row_data):
        print(f"Row {i}: {row_data}")

print("\nScanning for Date entries specifically...")
for i in range(200):
    row_data = df.iloc[i].astype(str).tolist()
    if any('DATE:' in str(x).upper() for x in row_data):
        print(f"Found Date Context at Row {i}: {row_data}")
