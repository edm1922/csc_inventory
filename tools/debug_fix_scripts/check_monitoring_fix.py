import pandas as pd
excel_file = "REQUEST SUPPLIES.xlsx"
try:
    df = pd.read_excel(excel_file, sheet_name="MONITORING ")
    print("Columns in Monitoring:")
    print(df.columns.tolist())
    print("\nFirst 15 rows with content:")
    # Drop rows that are all NaN to find the start
    df_clean = df.dropna(how='all')
    print(df_clean.head(15))
    
    # Check for dates
    print("\nDate column check:")
    # Usually dates are in the header or specific cells in these forms
    # Let's see if there's a column that looks like dates
    for col in df.columns:
        if 'date' in str(col).lower() or 'time' in str(col).lower():
            print(f"Potential date column: {col}")
except Exception as e:
    print(f"Error: {e}")
