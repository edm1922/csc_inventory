import pandas as pd
excel_file = "REQUEST SUPPLIES.xlsx"
df = pd.read_excel(excel_file, sheet_name="MONITORING ")

print("Sheet Shape:", df.shape)
print("\nFirst 100 rows of 'RECIPIENT' and 'DATE' context:")
# header is likely at row 5 (0-indexed)
# Let's find columns:
header_row = 5
cols = df.iloc[header_row].tolist()
print("Detected Header Row (6):", cols)

# Let's look at the raw rows around the dates
print("\nRows 0-10 raw:")
print(df.iloc[0:10])

# Let's extract all Recipient values found in the sheet
# Assuming Recipient is column 3 (Unnamed: 3)
recipients = df.iloc[header_row+1:, 3].dropna().unique()
print("\nUnique Recipients found in MONITORING sheet:")
print(recipients)
