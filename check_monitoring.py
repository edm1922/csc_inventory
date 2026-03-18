import pandas as pd
excel_file = "REQUEST SUPPLIES.xlsx"
try:
    xl = pd.ExcelFile(excel_file)
    if "Monitoring" in xl.sheet_names:
        df = pd.read_excel(excel_file, sheet_name="Monitoring")
        print("Columns in Monitoring:")
        print(df.columns.tolist())
        print("\nFirst 10 rows:")
        print(df.head(10))
    else:
        print("Sheet 'Monitoring' not found.")
except Exception as e:
    print(f"Error: {e}")
