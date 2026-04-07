import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os

# Scopes required for Google Sheets and Drive
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

class GoogleSyncService:
    def __init__(self, credentials_path):
        self.credentials_path = credentials_path
        self.gc = None
        self.sheet = None

    def authenticate(self):
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(f"Credentials file not found at {self.credentials_path}")
        
        creds = Credentials.from_service_account_file(self.credentials_path, scopes=SCOPES)
        self.gc = gspread.authorize(creds)

    def connect_to_sheet(self, sheet_url):
        if not self.gc:
            self.authenticate()
        self.sheet = self.gc.open_by_url(sheet_url).get_worksheet(0) # Open the first tab

    def fetch_new_responses(self):
        """
        Fetches all rows from the sheet. 
        We assume the first row is the header.
        We'll also look for a 'Synced' column to avoid duplicates.
        """
        if not self.sheet:
            raise ValueError("No sheet connected. Call connect_to_sheet first.")

        records = self.sheet.get_all_records()
        pending = []

        # Expected Headers based on user's Form screenshot:
        # Timestamp, Employee Name, Employee Role and shift, Item Requested, Department Area, Supervisor
        
        for idx, row in enumerate(records, start=2): # start=2 because row 1 is header
            # Check if row is mostly empty (skip empty bottom rows)
            if not any(str(val).strip() for val in row.values()):
                continue
                
            # Check if already synced
            if str(row.get('Synced', '')).upper() == 'YES':
                continue
            
            # Skip if no timestamp (usually means it's not a real response)
            if not row.get('Timestamp'):
                continue

            # Add the row index so we can mark it as synced later
            row['sheet_row_index'] = idx
            pending.append(row)

        return pending

    def mark_as_synced(self, row_index):
        """Marks a specific row in the Google Sheet as 'YES' in the Synced column."""
        if not self.sheet:
            return
        
        # Check if 'Synced' column exists in header
        headers = self.sheet.row_values(1)
        if 'Synced' not in headers:
            # Add it to the next empty column
            synced_col_idx = len(headers) + 1
            self.sheet.update_cell(1, synced_col_idx, 'Synced')
        else:
            synced_col_idx = headers.index('Synced') + 1

        self.sheet.update_cell(row_index, synced_col_idx, 'YES')

def parse_item_requested(text):
    """
    Parses strings like 'Ballpen - 5' or 'A4 Paper (10)' or 'Ballpen: 5'
    Returns (item_name, quantity)
    """
    import re
    text = text.strip()
    # Try to find a number first
    match = re.search(r'(\d+)', text)
    if match:
        qty = float(match.group(1))
        # Remove the number and common separators from the name
        name = re.sub(r'[\d\-\:\(\)]', '', text).strip()
        return name, qty
    return text, 1.0 # Default if no number found
