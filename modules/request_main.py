import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton, QTableWidget, 
                             QTableWidgetItem, QMessageBox, QHeaderView, QGroupBox, QFormLayout, 
                             QDialog, QDateEdit, QListWidget, QScrollArea, QFrame, QCompleter)
from PyQt6.QtCore import Qt, QDate, QTimer, QStringListModel
from PyQt6.QtGui import QDoubleValidator, QColor, QBrush

# Import backend logic
from database import (SessionLocal, Employee, SupplyRequest, Item, Department, 
                      RequestItem, Stock, Location, parse_frequency, normalize_frequency)

from sqlalchemy.orm import joinedload
from sqlalchemy import func
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from core.google_sync_service import GoogleSyncService, parse_item_requested

from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# Load environment variables
load_dotenv()

class GoogleSyncInboxDialog(QDialog):
    """Inbox to review and approve incoming Google Form requests."""
    def __init__(self, mode="SATELLITE", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setWindowTitle("📥 Google Forms Request Inbox")
        self.setMinimumSize(900, 500)
        
        self.layout = QVBoxLayout(self)
        
        # URL Input
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Google Sheet URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste your Responses Sheet URL here...")
        # Load from .env if available
        default_url = os.getenv("GOOGLE_SHEET_URL", "")
        self.url_input.setText(default_url)
        url_layout.addWidget(self.url_input)
        
        self.sync_btn = QPushButton("Check for New Requests")
        self.sync_btn.clicked.connect(self.sync_from_google)
        url_layout.addWidget(self.sync_btn)
        self.layout.addLayout(url_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Timestamp", "Employee", "Department", "Item & Qty", "Source", "Action", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.layout.addWidget(self.table)
        
        self.status_label = QLabel("Ready to sync.")
        self.layout.addWidget(self.status_label)
        
        self.pending_responses = []

    def sync_from_google(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please paste the Google Sheet URL first.")
            return
            
        self.status_label.setText("Syncing... please wait.")
        self.sync_btn.setEnabled(False)
        QApplication.processEvents()
        
        try:
            # Credentials path - using the one identified in the project
            creds_path = "inventorysync-491902-c629689ef8ea.json"
            service = GoogleSyncService(creds_path)
            service.connect_to_sheet(url)
            self.pending_responses = service.fetch_new_responses()
            
            self.display_responses()
            self.status_label.setText(f"Found {len(self.pending_responses)} new requests.")
        except Exception as e:
            QMessageBox.critical(self, "Sync Error", f"Failed to connect to Google Sheets:\n{str(e)}")
            self.status_label.setText("Sync failed.")
        finally:
            self.sync_btn.setEnabled(True)

    def display_responses(self):
        self.table.setRowCount(0)
        
        def find_val(row_dict, *keys):
            """Flexible header matching."""
            for k in row_dict.keys():
                for search_key in keys:
                    if search_key.lower() in k.lower():
                        return row_dict[k]
            return "N/A"

        for idx, row in enumerate(self.pending_responses):
            self.table.insertRow(idx)
            
            # Use flexible matching for the specific headers in the user's screenshot
            timestamp = find_val(row, "Timestamp")
            emp_name = find_val(row, "Employee Name")
            dept = find_val(row, "Department Area")
            item_text = find_val(row, "Item Requested")
            
            self.table.setItem(idx, 0, QTableWidgetItem(str(timestamp)))
            self.table.setItem(idx, 1, QTableWidgetItem(str(emp_name)))
            self.table.setItem(idx, 2, QTableWidgetItem(str(dept)))
            self.table.setItem(idx, 3, QTableWidgetItem(str(item_text)))
            
            # Source Location Dropdown
            source_combo = QComboBox()
            with SessionLocal() as session:
                locations = session.query(Location).all()
                for loc in locations:
                    source_combo.addItem(loc.name, loc.id)
                # Default to Warehouse if found
                w_idx = source_combo.findText("WAREHOUSE")
                if w_idx >= 0: source_combo.setCurrentIndex(w_idx)
            self.table.setCellWidget(idx, 4, source_combo)
            
            # Approve Button
            approve_btn = QPushButton("✅ Approve")
            approve_btn.setProperty("class", "primary")
            approve_btn.clicked.connect(lambda checked, r=row, i=idx, cb=source_combo: self.approve_request(r, i, cb))
            self.table.setCellWidget(idx, 5, approve_btn)
            
            self.table.setItem(idx, 6, QTableWidgetItem("Waiting review"))

    def approve_request(self, row_data, table_row, source_combo):
        """Commits the form data to the actual database."""
        try:
            source_id = source_combo.currentData()
            def find_val(row_dict, *keys):
                for k in row_dict.keys():
                    for search_key in keys:
                        if search_key.lower() in k.lower():
                            return row_dict[k]
                return ""

            # Split Item Requested into individual items
            full_item_text = str(find_val(row_data, "Item Requested")).strip()
            # Split by comma or semicolon
            raw_items = [i.strip() for i in full_item_text.replace(";", ",").split(",") if i.strip()]
            
            # Map Other Fields from screenshot
            emp_name = str(find_val(row_data, "Employee Name")).strip()
            role_val = str(find_val(row_data, "Employee Role")).strip()
            area = str(find_val(row_data, "Department Area")).strip()
            supervisor = str(find_val(row_data, "Supervisor")).strip()
            shift_val = str(find_val(row_data, "Shift")).strip()
            
            if not emp_name or emp_name == "N/A":
                QMessageBox.warning(self, "Invalid Data", "Could not find Employee Name in this row.")
                return

            with SessionLocal() as session:
                # 1. Get or Create Employee
                emp = session.query(Employee).filter(func.upper(Employee.name) == emp_name.upper()).first()
                if not emp:
                    emp = Employee(name=emp_name, role=role_val)
                    session.add(emp)
                    session.flush()
                
                # 2. Get or Create Department
                dept = session.query(Department).filter_by(area_name=area, role=role_val, supervisor=supervisor, shift=shift_val).first()
                if not dept:
                    dept = Department(area_name=area, role=role_val, supervisor=supervisor, shift=shift_val)
                    session.add(dept)
                    session.flush()
                
                # 3. Determine destination Location
                target_loc_name = "MAIN OFFICE" if self.mode == "MAIN_OFFICE" else "SATELLITE OFFICE"
                dest = session.query(Location).filter(func.upper(Location.name) == target_loc_name).first()
                if not dest: dest = session.query(Location).filter(Location.id != source_id).first()

                # 4. Create one Supply Request Header for the entire row
                new_req = SupplyRequest(
                    employee_id=emp.id,
                    department_id=dept.id,
                    request_date=datetime.now(),
                    source_location_id=source_id,
                    dest_location_id=dest.id if dest else None,
                    status="PENDING"
                )
                session.add(new_req)
                session.flush()
                
                # 5. Process each item in the comma-separated list
                created_count = 0
                for raw_item_str in raw_items:
                    item_name_raw, qty = parse_item_requested(raw_item_str)
                    
                    # Fuzzy match item name
                    # 1. Try exact match
                    item_obj = session.query(Item).filter(func.upper(Item.name) == item_name_raw.upper()).first()
                    # 2. Try partial match if no exact match (e.g. "Ballpen" matches "BALLPEN (HBW)")
                    if not item_obj:
                        item_obj = session.query(Item).filter(Item.name.ilike(f"%{item_name_raw}%")).first()
                    
                    # 3. Create if still not found
                    if not item_obj:
                        item_obj = Item(name=item_name_raw.upper())
                        session.add(item_obj)
                        session.flush()
                    
                    # Create Request Item
                    ri = RequestItem(
                        request_id=new_req.id,
                        item_id=item_obj.id,
                        quantity=qty,
                        is_refill_request=False,
                        frequency="N/A"
                    )
                    session.add(ri)
                    created_count += 1
                
                if created_count == 0:
                    session.rollback()
                    QMessageBox.warning(self, "No Items", "No valid items found in the 'Item Requested' field.")
                    return
                    
                session.commit()
                
            # 7. Mark as synced in Google Sheet
            sheet_url = self.url_input.text().strip()
            row_idx = row_data.get('sheet_row_index')
            if sheet_url and row_idx:
                try:
                    creds_path = "inventorysync-491902-c629689ef8ea.json"
                    service = GoogleSyncService(creds_path)
                    service.connect_to_sheet(sheet_url)
                    service.mark_as_synced(row_idx)
                except Exception as sync_err:
                    print(f"Sync write-back failed: {sync_err}")

            # Update UI
            self.table.item(table_row, 6).setText("✅ APPROVED")
            self.table.item(table_row, 6).setForeground(QColor("green"))
            self.table.cellWidget(table_row, 5).setEnabled(False)
            source_combo.setEnabled(False)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to approve request: {str(e)}")

class EditRequestItemDialog(QDialog):
    """A dialog to edit all fields of a specific request item."""
    def __init__(self, request_item_id=None, employee_id=None, mode="SATELLITE", parent=None):
        super().__init__(parent)
        self.request_item_id = request_item_id
        self.employee_id = employee_id
        self.mode = mode
        self.setWindowTitle("Add New Request" if not request_item_id else "Edit Request Details")
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        
        self.name_input = QComboBox()
        self.name_input.setEditable(True)
        self.role_input = QLineEdit()
        self.area_input = QLineEdit()
        self.shift_input = QLineEdit()
        self.supervisor_input = QLineEdit()
        self.item_name_input = QComboBox()
        self.item_name_input.setEditable(True)
        
        self.qty_input = QLineEdit()
        self.qty_input.setValidator(QDoubleValidator(0.1, 999.0, 2))
        
        self.frequency_input = QComboBox()
        self.frequency_input.setEditable(True)
        self.frequency_input.addItems(["1 WEEK", "2 WEEKS", "ONCE A WEEK", "TWICE A WEEK", "1 MONTH", "ONCE A MONTH", "UNTIL DEFECTIVE", "REFILL"])
        
        self.source_loc_input = QComboBox()
        self.dest_loc_input = QComboBox()
        
        form.addRow("Request Date:", self.date_edit)
        form.addRow("Employee Name:", self.name_input)
        
        form.addRow("Employee Role:", self.role_input)
        form.addRow("Area/Department:", self.area_input)
        form.addRow("Shift:", self.shift_input)
        form.addRow("Supervisor:", self.supervisor_input)
            
        form.addRow("Item Name:", self.item_name_input)
        form.addRow("Quantity:", self.qty_input)
        
        form.addRow("Frequency:", self.frequency_input)
            
        form.addRow("Fulfillment Source:", self.source_loc_input)
        form.addRow("Requesting Office:", self.dest_loc_input)
        
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        save_btn = QPushButton("Save Changes")
        save_btn.setProperty("class", "primary")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
        
        # Initialize dropdowns
        self.load_dropdown_data()
        
        if self.request_item_id:
            self.load_current_data()
        else:
            self.date_edit.setDate(QDate.currentDate())
            self.qty_input.setText("1.0")

    def load_dropdown_data(self):
        with SessionLocal() as session:
            # Fetch both name and description
            items = session.query(Item.name, Item.description).order_by(Item.name).all()
            for name, desc in items:
                display = f"{name} ({desc})" if desc else name
                self.item_name_input.addItem(display, {"name": name, "description": desc or ""})
            
            locations = session.query(Location).all()
            for loc in locations:
                self.source_loc_input.addItem(loc.name, loc.id)
                self.dest_loc_input.addItem(loc.name, loc.id)
                
            # Load employee names for autofill
            employees = session.query(Employee.name).order_by(Employee.name).all()
            self.name_input.addItems([e[0] for e in employees])
            self.name_input.setCurrentText("") # Start empty
            self.name_input.currentTextChanged.connect(self.autofill_employee_details)
            
            # Prepopulate area if adding for specific employee
            if self.employee_id and not self.request_item_id:
                emp = session.query(Employee).get(self.employee_id)
                if emp:
                    self.name_input.setCurrentText(emp.name)
                
                last_req = session.query(SupplyRequest).options(joinedload(SupplyRequest.department)).filter_by(employee_id=self.employee_id).order_by(SupplyRequest.id.desc()).first()
                if last_req and self.mode == "SATELLITE":
                    if last_req.department:
                        self.role_input.setText(last_req.department.role or emp.role or "")
                        self.area_input.setText(last_req.department.area_name or "")
                        self.shift_input.setText(last_req.department.shift or "")
                        self.supervisor_input.setText(last_req.department.supervisor or "")

    def autofill_employee_details(self, name):
        name = name.strip()
        if not name: return
        
        # Don't autofill if we are in "Edit Mode" (already loaded specific data)
        if self.request_item_id: return

        with SessionLocal() as session:
            emp = session.query(Employee).filter(func.upper(Employee.name) == name.upper()).first()
            if emp:
                # Fetch last request for department info
                last_req = session.query(SupplyRequest).options(joinedload(SupplyRequest.department)).filter_by(employee_id=emp.id).order_by(SupplyRequest.id.desc()).first()
                if last_req and last_req.department:
                    self.role_input.setText(last_req.department.role or emp.role or "")
                    self.area_input.setText(last_req.department.area_name or "")
                    self.shift_input.setText(last_req.department.shift or "")
                    self.supervisor_input.setText(last_req.department.supervisor or "")
                else:
                    self.role_input.setText(emp.role or "")

    def load_current_data(self):
        with SessionLocal() as session:
            req = session.query(RequestItem).options(
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.department),
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.source_location),
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.dest_location),
                joinedload(RequestItem.item)
            ).get(self.request_item_id)
            
            if req:
                self.name_input.setCurrentText(req.supply_request.employee.name)
                self.role_input.setText(req.supply_request.department.role or req.supply_request.employee.role or "")
                rd = req.supply_request.request_date
                self.date_edit.setDate(QDate(rd.year, rd.month, rd.day))
                display = f"{req.item.name} ({req.item.description})" if req.item.description else req.item.name
                self.item_name_input.setCurrentText(display)
                self.qty_input.setText(str(req.quantity))
                
                self.area_input.setText(req.supply_request.department.area_name or "")
                self.shift_input.setText(req.supply_request.department.shift or "")
                self.supervisor_input.setText(req.supply_request.department.supervisor or "")
                self.frequency_input.setCurrentText(req.frequency or "")
                
                # Set Locations by ID (much safer than names)
                if req.supply_request.source_location_id:
                    idx = self.source_loc_input.findData(req.supply_request.source_location_id)
                    if idx >= 0: self.source_loc_input.setCurrentIndex(idx)
                
                if req.supply_request.dest_location_id:
                    idx = self.dest_loc_input.findData(req.supply_request.dest_location_id)
                    if idx >= 0: self.dest_loc_input.setCurrentIndex(idx)

    def get_data(self):
        data = {
            "name": self.name_input.currentText().strip().upper(),
            "role": self.role_input.text().strip(),
            "date": self.date_edit.date().toPyDate(),
            # Extract name and description from currentData() or parse currentText()
            "item_name": self.item_name_input.currentData()["name"] if self.item_name_input.currentData() else self.item_name_input.currentText().strip().upper(),
            "item_desc": self.item_name_input.currentData()["description"] if self.item_name_input.currentData() else "",
            "qty": float(self.qty_input.text() or 0),
            "source_loc_id": self.source_loc_input.currentData(),
            "dest_loc_id": self.dest_loc_input.currentData(),
            "area": "N/A",
            "shift": "N/A",
            "supervisor": "N/A",
            "refill": False,
            "freq": "N/A"
        }
        
        data["area"] = self.area_input.text().strip()
        data["shift"] = self.shift_input.text().strip()
        data["supervisor"] = self.supervisor_input.text().strip()
        data["freq"] = normalize_frequency(self.frequency_input.currentText().strip())
            
        return data

class EmployeeDetailsDialog(QDialog):
    def __init__(self, employee_id, employee_name, mode="SATELLITE", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setWindowTitle(f"Request History: {employee_name}")
        self.setGeometry(200, 200, 800, 400)
        self.employee_id = employee_id
        
        layout = QVBoxLayout(self)
        
        # Employee Info Header
        self.info_box = QGroupBox("Employee Details")
        self.info_layout = QHBoxLayout(self.info_box)
        
        self.label_role = QLabel("<b>Role:</b> Loading...")
        self.label_area = QLabel("<b>Area:</b> Loading...")
        self.label_shift = QLabel("<b>Shift:</b> Loading...")
        self.label_super = QLabel("<b>Supervisor:</b> Loading...")
        self.label_first = QLabel("<b>First Issuance:</b> N/A")
        self.label_total = QLabel("<b>Total Items:</b> 0")
        
        header_labels = [self.label_role, self.label_area, self.label_shift, self.label_super, self.label_first, self.label_total]
        
        for lbl in header_labels:
            lbl.setTextFormat(Qt.TextFormat.RichText)
            self.info_layout.addWidget(lbl)
            
        layout.addWidget(self.info_box)
        
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Date", "Role", "Area", "Shift", "Item Requested", "Qty", "Frequency", "Status", "Req ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(8, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems) # Select cells, not just rows
        self.table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
        self.table.itemChanged.connect(self.save_cell_edit)
        layout.addWidget(self.table)
        
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("&Add New Item")
        self.add_btn.setProperty("class", "primary")
        self.add_btn.clicked.connect(self.add_new_request_item)
        
        self.edit_btn = QPushButton("&Edit Selected")
        self.edit_btn.setProperty("class", "secondary")
        self.edit_btn.clicked.connect(self.edit_selected_request)
        
        self.delete_btn = QPushButton("&Delete Selected")
        self.delete_btn.setProperty("class", "danger")
        self.delete_btn.clicked.connect(self.delete_selected_request)
        
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

        self.load_data()

    def load_data(self):
        self.table.blockSignals(True) # Prevent save_cell_edit from firing during load
        with SessionLocal() as session:
            # Fetch Employee Metadata first
            employee = session.query(Employee).options(
                joinedload(Employee.requests).joinedload(SupplyRequest.department)
            ).filter(Employee.id == self.employee_id).first()
            
            if employee:
                if employee.requests:
                    latest_dept = employee.requests[-1].department
                    self.label_role.setText(f"<b>Role:</b> {latest_dept.role or employee.role or 'N/A'}")
                    self.label_area.setText(f"<b>Area:</b> {latest_dept.area_name or 'N/A'}")
                    self.label_shift.setText(f"<b>Shift:</b> {latest_dept.shift or 'N/A'}")
                    self.label_super.setText(f"<b>Supervisor:</b> {latest_dept.supervisor or 'N/A'}")

            requests = session.query(RequestItem).join(SupplyRequest).filter(
                SupplyRequest.employee_id == self.employee_id
            ).options(
                joinedload(RequestItem.item),
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.department),
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.source_location)
            ).order_by(RequestItem.id.desc()).all()
            
            # Pre-fetch ALL stock levels to allow dynamic highlighting based on source
            all_stocks = {} # {(location_id, item_id): quantity}
            stocks = session.query(Stock).all()
            for s in stocks:
                all_stocks[(s.location_id, s.item_id)] = s.quantity
            
            # Master Item Check (including descriptions for variants)
            all_master_items = session.query(Item.name, Item.description).order_by(Item.name).all()
            all_item_names = [f"{i.name} ({i.description})" if i.description else i.name for i in all_master_items]

            if requests:
                # Calculate tracking metrics
                first_date = min(r.supply_request.request_date for r in requests)
                total_qty = sum(r.quantity for r in requests)
                self.label_first.setText(f"<b>First Issuance:</b> {first_date.strftime('%Y-%m-%d')}")
                self.label_total.setText(f"<b>Total Items:</b> {total_qty:.0f}")

            self.table.setRowCount(0)
            for row_idx, req in enumerate(requests):
                self.table.insertRow(row_idx)
                
                date_str = req.supply_request.request_date.strftime("%Y-%m-%d")
                role_str = req.supply_request.department.role or ""
                area_name = req.supply_request.department.area_name or "Unknown"
                shift_val = req.supply_request.department.shift or ""
                
                # Determine Highlight Color based on its actual Fulfillment Source
                bg_color = None
                source_id = req.supply_request.source_location_id
                
                # Check if item exists at the selected source
                if (source_id, req.item_id) not in all_stocks:
                    bg_color = QColor("#ffcdd2") # Light Red (Non-existing at Source)
                else:
                    qty = all_stocks.get((source_id, req.item_id), 0.0)
                    if qty <= 0:
                        bg_color = QColor("#ffe0b2") # Light Orange (Out of Stock at Source)
                    else:
                        bg_color = QColor("#c8e6c9") # Light Green (In Stock at Source)

                self.table.setItem(row_idx, 0, QTableWidgetItem(date_str))
                self.table.setItem(row_idx, 1, QTableWidgetItem(role_str))
                self.table.setItem(row_idx, 2, QTableWidgetItem(area_name))
                self.table.setItem(row_idx, 3, QTableWidgetItem(shift_val))
                
                # Show name and description collectively in table for clarity
                item_name_text = f"{req.item.name} ({req.item.description})" if req.item.description else req.item.name
                if bg_color and bg_color.name() == "#ffcdd2": # Light Red
                    # CREATE SUGGESTION DROPDOWN
                    combo = QComboBox()
                    # Pre-fill suggestions
                    combo.addItems(all_item_names)
                    
                    # Add current invalid name as first reminder if not present
                    if item_name_text not in all_item_names:
                        combo.insertItem(0, f"🔍 FIX: {item_name_text}")
                        combo.setCurrentIndex(0)
                    else:
                        combo.setCurrentText(item_name_text)

                    combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                    combo.setEnabled(True)
                    
                    # Style to match table cell
                    combo.setStyleSheet("""
                        QComboBox { background-color: #ffcdd2; color: #b71c1c; border: 1px solid #ef9a9a; border-radius: 4px; padding: 2px; }
                        QComboBox::drop-down { border: none; }
                        QComboBox QAbstractItemView { selection-background-color: #ef9a9a; selection-color: black; }
                    """)
                    
                    req_id = req.id 
                    # Use activated(int) or textActivated(str)
                    combo.textActivated.connect(lambda name, rid=req_id, c=combo: self.resolve_item_mismatch(rid, c, name))
                    
                    self.table.setCellWidget(row_idx, 4, combo)
                else:
                    item_cell = QTableWidgetItem(item_name_text)
                    if bg_color:
                        item_cell.setBackground(QBrush(bg_color))
                    self.table.setItem(row_idx, 4, item_cell)
                self.table.setItem(row_idx, 5, QTableWidgetItem(f"{req.quantity:.2f}"))
                self.table.setItem(row_idx, 6, QTableWidgetItem(req.frequency or ""))
                
                # --- NEW: STATUS MARKING SYSTEM FOR CUSTODIAN ---
                status_val = req.supply_request.status or "PENDING"
                # Handle both FULFILLED and old DONE/DELIVERED statuses as "undoable"
                is_fulfilled = status_val in ["FULFILLED", "DONE", "DELIVERED"]
                
                status_btn = QPushButton("🔄 Undo" if is_fulfilled else status_val)
                status_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                
                # Dynamic Styling based on Status
                if is_fulfilled:
                    status_btn.setStyleSheet("background-color: #c8e6c9; color: #2e7d32; font-weight: bold; border-radius: 4px;")
                    status_btn.setToolTip("Click to undo fulfillment and restore stock.")
                else:
                    status_btn.setStyleSheet("background-color: #ffcdd2; color: #b71c1c; font-weight: bold; border-radius: 4px;")
                
                status_btn.clicked.connect(lambda checked, r=req: self.mark_as_fulfilled(r))
                self.table.setCellWidget(row_idx, 7, status_btn)
                
                # Set Request ID in Hidden Column (index 8)
                self.table.setItem(row_idx, 8, QTableWidgetItem(str(req.id))) 
                
                # Make non-editable columns read-only
                for col in [0, 4, 7, 8]: 
                    it = self.table.item(row_idx, col)
                    if it: it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.table.blockSignals(False)

    def mark_as_fulfilled(self, request_item):
        """Toggles fulfillment status: Marks as FULFILLED/Deducts stock OR Restores to PENDING/Returns stock."""
        with SessionLocal() as session:
            try:
                # Re-fetch from DB to ensure fresh state
                req_item = session.query(RequestItem).options(
                    joinedload(RequestItem.supply_request),
                    joinedload(RequestItem.item),
                    joinedload(RequestItem.supply_request).joinedload(SupplyRequest.source_location)
                ).get(request_item.id)
                
                current_status = req_item.supply_request.status
                is_undoing = current_status in ["FULFILLED", "DONE", "DELIVERED"]

                if is_undoing:
                    ans = QMessageBox.question(self, "Undo Fulfillment?", 
                                             f"Restore '{req_item.item.name}' to PENDING?\n\n"
                                             f"This will ADD {req_item.quantity} units back to {req_item.supply_request.source_location.name}.",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if ans != QMessageBox.StandardButton.Yes: return

                    # Add stock back
                    source_id = req_item.supply_request.source_location_id
                    stock = session.query(Stock).filter_by(item_id=req_item.item_id, location_id=source_id).first()
                    if stock:
                        stock.quantity += req_item.quantity
                    else:
                        new_stock = Stock(item_id=req_item.item_id, location_id=source_id, quantity=req_item.quantity)
                        session.add(new_stock)
                    
                    req_item.supply_request.status = "PENDING"
                    msg = "Fulfillment undone. Stock has been restored."
                else:
                    ans = QMessageBox.question(self, "Confirm Fulfillment", 
                                             f"Mark '{req_item.item.name}' as FULFILLED and deduct quantity from inventory?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if ans != QMessageBox.StandardButton.Yes: return

                    # Check Inventory Safeguard
                    source_id = req_item.supply_request.source_location_id
                    stock = session.query(Stock).filter_by(item_id=req_item.item_id, location_id=source_id).first()
                    
                    current_qty = stock.quantity if stock else 0.0
                    if current_qty < req_item.quantity:
                        QMessageBox.warning(self, "Insufficient Stock", 
                                           f"Cannot fulfill: Only {current_qty} units available at the selected source.\n"
                                           f"Quantity Needed: {req_item.quantity}\n\n"
                                           "Please restock the inventory source first.")
                        return

                    # Deduct Stock
                    if stock:
                        stock.quantity -= req_item.quantity
                    else:
                        new_stock = Stock(item_id=req_item.item_id, location_id=source_id, quantity=-req_item.quantity)
                        session.add(new_stock)

                    req_item.supply_request.status = "FULFILLED"
                    msg = "Request fulfilled! Inventory updated."

                session.commit()
                QMessageBox.information(self, "Success", msg)
                self.load_data()
                if self.parent(): self.parent().refresh_table()
                
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"Action failed: {str(e)}")

    def resolve_item_mismatch(self, request_item_id, combo_box, selected_name=None):
        """Updates the RequestItem's linked item when a suggestion is picked."""
        if selected_name is None:
            selected_name = combo_box.currentText()
            
        selected_name = selected_name.strip()
        if "🔍 NOT FOUND" in selected_name: return # Still not found
        
        with SessionLocal() as session:
            try:
                # 1. Parse name and description if present in "NAME (DESC)" format
                name = selected_name
                description = ""
                if "(" in selected_name and selected_name.endswith(")"):
                    name = selected_name[:selected_name.rfind("(")].strip()
                    description = selected_name[selected_name.rfind("(")+1:-1].strip()

                # 2. Fetch the chosen item variant from master list
                item_obj = session.query(Item).filter(
                    func.upper(Item.name) == name.upper(),
                    func.upper(Item.description) == description.upper()
                ).first()
                if not item_obj: return
                
                # 2. Update the RequestItem link
                req_item = session.query(RequestItem).get(request_item_id)
                if req_item:
                    req_item.item_id = item_obj.id
                    session.commit()
                    # Refresh to show new status (likely green/orange)
                    self.load_data()
                    if self.parent():
                        self.parent().refresh_table()
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to match item: {str(e)}")

    def confirm_selected_delivery(self):
        """Hidden feature being removed as column is gone."""
        pass

    def save_cell_edit(self, item):
        """Triggered when a cell is edited manually."""
        row = item.row()
        col = item.column()
        new_val = item.text().strip()
        
        # Get the ID of the RequestItem (stored in hidden col 8)
        id_item = self.table.item(row, 8)
        if not id_item: return
        request_item_id = int(id_item.text())

        with SessionLocal() as session:
            try:
                req_item = session.query(RequestItem).options(
                    joinedload(RequestItem.supply_request).joinedload(SupplyRequest.department),
                    joinedload(RequestItem.supply_request).joinedload(SupplyRequest.employee)
                ).get(request_item_id)
                
                if not req_item: return

                if col in [1, 2, 3]: # Metadata (Role, Area, Shift)
                    # Current values from the linked department
                    role = req_item.supply_request.department.role
                    area = req_item.supply_request.department.area_name
                    shift = req_item.supply_request.department.shift
                    supervisor = req_item.supply_request.department.supervisor
                    
                    if col == 1: 
                        role = new_val
                        # Also update the Master Employee Record for this employee
                        if req_item.supply_request.employee:
                            req_item.supply_request.employee.role = new_val
                    elif col == 2: 
                        area = new_val
                    elif col == 3: 
                        shift = new_val
                    
                    # Find or Create Department (to avoid affecting other employees sharing this group)
                    new_dept = session.query(Department).filter_by(
                        role=role,
                        area_name=area,
                        shift=shift,
                        supervisor=supervisor
                    ).first()
                    
                    if not new_dept:
                        new_dept = Department(
                            role=role,
                            area_name=area,
                            shift=shift,
                            supervisor=supervisor
                        )
                        session.add(new_dept)
                        session.flush()
                    
                    req_item.supply_request.department = new_dept
                elif col == 5: # Qty
                    try:
                        req_item.quantity = float(new_val)
                    except ValueError:
                        QMessageBox.warning(self, "Invalid Input", "Quantity must be a number.")
                        self.load_data()
                        return
                elif col == 6: # Frequency
                    new_val = normalize_frequency(new_val)
                    req_item.frequency = new_val
                    # Refresh the cell display with normalized value
                    self.table.blockSignals(True)
                    item.setText(new_val)
                    self.table.blockSignals(False)
                
                session.commit()
                # Optional visual feedback or just stay quiet
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Database Error", f"Failed to save change:\n{str(e)}")
                self.load_data()


    def edit_selected_request(self):
        """Opens a comprehensive dialog to edit all fields of the selected request."""
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a request to edit.")
            return
            
        row = selected_items[0].row()
        request_item_id = int(self.table.item(row, 8).text())
        
        dialog = EditRequestItemDialog(request_item_id, mode=self.mode, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            with SessionLocal() as session:
                try:
                    req_item = session.query(RequestItem).options(
                        joinedload(RequestItem.supply_request).joinedload(SupplyRequest.department),
                        joinedload(RequestItem.item)
                    ).get(request_item_id)
                    
                    if req_item:
                        # Update Employee / Reassign
                        old_emp = req_item.supply_request.employee
                        new_name = data["name"]
                        
                        if old_emp.name != new_name:
                            # Check if new name exists
                            existing_emp = session.query(Employee).filter_by(name=new_name).first()
                            if existing_emp:
                                # Reassign this request to existing employee
                                req_item.supply_request.employee = existing_emp
                            else:
                                # Rename existing employee object (affects all their requests)
                                old_emp.name = new_name
                        
                        # Update Supply Request (Date & Locations)
                        d = data["date"]
                        new_dt = datetime(d.year, d.month, d.day)
                        req_item.supply_request.request_date = new_dt
                        req_item.supply_request.source_location_id = data["source_loc_id"]
                        req_item.supply_request.dest_location_id = data["dest_loc_id"]
                        
                        # Find or Create Department (Isolation Fix)
                        new_dept = session.query(Department).filter_by(
                            role=data["role"],
                            area_name=data["area"],
                            shift=data["shift"],
                            supervisor=data["supervisor"]
                        ).first()
                        
                        if not new_dept:
                            new_dept = Department(
                                role=data["role"],
                                area_name=data["area"],
                                shift=data["shift"],
                                supervisor=data["supervisor"]
                            )
                            session.add(new_dept)
                            session.flush()
                        
                        req_item.supply_request.department = new_dept
                        
                        # Update Item (check if exists by name and description)
                        item_obj = session.query(Item).filter(
                            Item.name == data["item_name"],
                            Item.description == data["item_desc"]
                        ).first()
                        if not item_obj:
                            item_obj = Item(name=data["item_name"], description=data["item_desc"])
                            session.add(item_obj)
                            session.flush()
                        
                        req_item.item_id = item_obj.id
                        req_item.quantity = data["qty"]
                        
                        req_item.frequency = data["freq"]
                        req_item.is_refill_request = data.get("refill", False)
                        
                        session.commit()
                        self.load_data()
                        if self.parent():
                            self.parent().refresh_table()
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Error", f"Failed to update request: {str(e)}")

    def add_new_request_item(self):
        """Opens a dialog to add a new request item for this employee."""
        dialog = EditRequestItemDialog(employee_id=self.employee_id, mode=self.mode, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            with SessionLocal() as session:
                try:
                    # 1. Find or Create Employee by Name
                    new_name = data["name"]
                    emp = session.query(Employee).filter(func.upper(Employee.name) == new_name.upper()).first()
                    if not emp:
                        emp = Employee(name=new_name, role=data["role"])
                        session.add(emp)
                        session.flush()
                    
                    # 2. Get or Create Department
                    dept = session.query(Department).filter_by(
                        role=data["role"],
                        area_name=data["area"],
                        shift=data["shift"],
                        supervisor=data["supervisor"]
                    ).first()
                    
                    if not dept:
                        dept = Department(
                            role=data["role"],
                            area_name=data["area"],
                            shift=data["shift"],
                            supervisor=data["supervisor"]
                        )
                        session.add(dept)
                        session.flush()

                    # 2. Get or Create Item (check if exists by name and description)
                    item_obj = session.query(Item).filter(
                        Item.name == data["item_name"],
                        Item.description == data["item_desc"]
                    ).first()
                    if not item_obj:
                        item_obj = Item(name=data["item_name"], description=data["item_desc"])
                        session.add(item_obj)
                        session.flush()

                    # 3. Create or Find Supply Request Header for that date/emp/dept
                    # To keep it simple, we'll just create a new one to avoid merging complexity
                    d = data["date"]
                    new_dt = datetime(d.year, d.month, d.day)
                    supply_req = SupplyRequest(
                        employee_id=self.employee_id,
                        department_id=dept.id,
                        request_date=new_dt,
                        source_location_id=data["source_loc_id"],
                        dest_location_id=data["dest_loc_id"]
                    )
                    session.add(supply_req)
                    session.flush()

                    # 4. Create Request Item
                    req_item = RequestItem(
                        request_id=supply_req.id,
                        item_id=item_obj.id,
                        quantity=data["qty"],
                        frequency=data["freq"],
                        is_refill_request=data.get("refill", False)
                    )
                    session.add(req_item)
                    
                    session.commit()
                    self.load_data()
                    if self.parent():
                        self.parent().refresh_table()
                    QMessageBox.information(self, "Success", "New request item added successfully.")
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Error", f"Failed to add request: {str(e)}")


    def delete_selected_request(self):
        """Deletes all selected requests after confirmation."""
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select one or more rows to delete.")
            return

        # Identify unique rows to avoid double-processing
        rows = sorted(list(set(item.row() for item in selected_items)), reverse=True)
        count = len(rows)
        
        msg = f"Are you sure you want to permanently delete these {count} selected item(s)?"
        ans = QMessageBox.question(self, "Confirm Batch Delete", msg,
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if ans == QMessageBox.StandardButton.Yes:
            with SessionLocal() as session:
                try:
                    for row in rows:
                        req_item_id = int(self.table.item(row, 8).text())
                        req_item = session.query(RequestItem).options(
                            joinedload(RequestItem.supply_request)
                        ).get(req_item_id)
                        
                        if req_item:
                            supply_req = req_item.supply_request
                            session.delete(req_item)
                            session.flush() 
                            
                            # If this was the last item in that supply request, delete the request head too
                            if not supply_req.requested_items:
                                session.delete(supply_req)
                    
                    session.commit()
                    self.load_data()
                    if self.parent():
                        self.parent().refresh_table()
                    QMessageBox.information(self, "Deleted", f"{count} request(s) successfully removed.")
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Error", f"Failed to delete requests: {str(e)}")

class PendingRequestsDialog(QDialog):
    """A unified dashboard for custodians to view FULFILLED issuance log requests."""
    def __init__(self, mode="SATELLITE", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setWindowTitle("📋 Issuance Log Dashboard")
        self.setMinimumSize(1000, 600)
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Supply Issuance Log")
        title.setObjectName("headerTitle")
        title.setStyleSheet("#headerTitle { font-size: 20px; font-weight: bold; color: #1E3A5F; }")
        header.addWidget(title)
        
        header.addStretch()
        self.refresh_btn = QPushButton("🔄 Refresh List")
        self.refresh_btn.setProperty("class", "secondary")
        self.refresh_btn.clicked.connect(self.load_data)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Date", "Employee", "Department/Area", "Item Requested", "Qty", "Source", "Action", "ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(7, True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.table)
        
        footer = QHBoxLayout()
        hint = QLabel("<i>Note: Fulfilling items must be done from the main employee dashboard now. This log shows finalized issuances.</i>")
        footer.addWidget(hint)
        footer.addStretch()
        
        self.print_btn = QPushButton("🖨️ Print Issuance Log")
        self.print_btn.setStyleSheet("background-color: #1565C0; color: white; font-weight: bold;")
        self.print_btn.clicked.connect(self.print_issuance_log)
        footer.addWidget(self.print_btn)
        
        self.bulk_undo_btn = QPushButton("⏪ Bulk Undo Selected")
        self.bulk_undo_btn.setStyleSheet("background-color: #ef6c00; color: white; font-weight: bold;")
        self.bulk_undo_btn.clicked.connect(lambda: self.batch_fulfill(action='UNDO'))
        footer.addWidget(self.bulk_undo_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        footer.addWidget(self.close_btn)
        layout.addLayout(footer)
        
        self.load_data()

    def load_data(self):
        self.table.setRowCount(0)
        with SessionLocal() as session:
            # Query recent request items for the current office mode (both Pending and Fulfilled)
            target_loc_name = "MAIN OFFICE" if self.mode == "MAIN_OFFICE" else "SATELLITE OFFICE"
            
            # Show requests from the last 200 entries for performance/relevance
            activity_items = session.query(RequestItem).join(SupplyRequest).join(Location, SupplyRequest.dest_location_id == Location.id).filter(
                Location.name == target_loc_name,
                SupplyRequest.status.in_(["FULFILLED", "DONE", "DELIVERED"])
            ).options(
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.source_location)
            ).order_by(SupplyRequest.request_date.desc()).limit(200).all()
            
            for row_idx, ri in enumerate(activity_items):
                self.table.insertRow(row_idx)
                
                date_str = ri.supply_request.request_date.strftime("%Y-%m-%d")
                emp_name = ri.supply_request.employee.name
                dept_area = f"{ri.supply_request.department.area_name}"
                item_display = f"{ri.item.name} ({ri.item.description})" if ri.item.description else ri.item.name
                
                self.table.setItem(row_idx, 0, QTableWidgetItem(date_str))
                self.table.setItem(row_idx, 1, QTableWidgetItem(emp_name))
                self.table.setItem(row_idx, 2, QTableWidgetItem(dept_area))
                self.table.setItem(row_idx, 3, QTableWidgetItem(item_display))
                self.table.setItem(row_idx, 4, QTableWidgetItem(f"{ri.quantity:.2f}"))
                self.table.setItem(row_idx, 5, QTableWidgetItem(ri.supply_request.source_location.name))
                
                # Fulfill / Undo Button
                status_val = ri.supply_request.status or "PENDING"
                is_fulfilled = status_val in ["FULFILLED", "DONE", "DELIVERED"]
                
                btn = QPushButton("🔄 Undo Fulfillment")
                btn.setStyleSheet("background-color: #ef6c00; color: white; font-weight: bold; border-radius: 4px;")
                btn.setToolTip("Click to undo fulfillment and restore stock.")
                
                btn.clicked.connect(lambda checked, item=ri: self.fulfill_item(item))
                self.table.setCellWidget(row_idx, 6, btn)
                
                self.table.setItem(row_idx, 7, QTableWidgetItem(str(ri.id)))

    def print_issuance_log(self):
        data_list = []
        for row in range(self.table.rowCount()):
            data_list.append({
                "date": self.table.item(row, 0).text(),
                "employee": self.table.item(row, 1).text(),
                "department": self.table.item(row, 2).text(),
                "item": self.table.item(row, 3).text(),
                "qty": self.table.item(row, 4).text(),
                "source": self.table.item(row, 5).text()
            })
            
        if not data_list:
            QMessageBox.warning(self, "No Data", "There is no issuance data to print.")
            return
            
        filename = f"ISSUANCE_LOG_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        try:
            c = canvas.Canvas(filename, pagesize=landscape(letter))
            width, height = landscape(letter)
            
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(width/2, height - 40, "SUPPLY ISSUANCE LOG")
            
            c.setFont("Helvetica-Bold", 10)
            y = height - 80
            
            # Headers
            c.drawString(40, y, "Date")
            c.drawString(120, y, "Employee")
            c.drawString(280, y, "Department/Area")
            c.drawString(450, y, "Item Description")
            c.drawString(630, y, "Qty Released")
            c.drawString(700, y, "Fulfillment Source")
            
            y -= 15
            c.line(40, y + 5, width - 40, y + 5)
            y -= 15
            
            c.setFont("Helvetica", 9)
            for item in data_list:
                if y < 80: # Leave more space for summary if near end
                    c.showPage()
                    c.setFont("Helvetica-Bold", 10)
                    y = height - 50
                    c.drawString(40, y, "Date")
                    c.drawString(120, y, "Employee")
                    c.drawString(280, y, "Department/Area")
                    c.drawString(450, y, "Item Description")
                    c.drawString(630, y, "Qty Released")
                    c.drawString(700, y, "Fulfillment Source")
                    y -= 15
                    c.line(40, y + 5, width - 40, y + 5)
                    y -= 15
                    c.setFont("Helvetica", 9)
                
                # Truncate strings to fit
                emp = item["employee"][:25] + "..." if len(item["employee"]) > 25 else item["employee"]
                dept = item["department"][:25] + "..." if len(item["department"]) > 25 else item["department"]
                itm = item["item"][:35] + "..." if len(item["item"]) > 35 else item["item"]
                
                c.drawString(40, y, item["date"])
                c.drawString(120, y, emp)
                c.drawString(280, y, dept)
                c.drawString(450, y, itm)
                c.drawString(630, y, item["qty"])
                c.drawString(700, y, item["source"])
                y -= 20

            # --- Aggregated Summary Section ---
            # 1. Calculate Summary Totals
            item_summary = {}
            for item in data_list:
                name = item["item"]
                qty = float(item["qty"])
                if name not in item_summary:
                    item_summary[name] = {"released": 0.0, "lacking": 0.0}
                item_summary[name]["released"] += qty

            # 2. Query DB for Lacking (Pending) counts
            target_loc_name = "MAIN OFFICE" if self.mode == "MAIN_OFFICE" else "SATELLITE OFFICE"
            with SessionLocal() as session:
                pending_items = session.query(Item.name, Item.description, func.sum(RequestItem.quantity)) \
                    .join(RequestItem).join(SupplyRequest).join(Location, SupplyRequest.dest_location_id == Location.id) \
                    .filter(Location.name == target_loc_name) \
                    .filter(SupplyRequest.status.in_([None, "PENDING"])) \
                    .group_by(Item.name, Item.description).all()
                
                lacking_map = {}
                for name, desc, total_qty in pending_items:
                    display = f"{name} ({desc})" if desc else name
                    lacking_map[display] = float(total_qty or 0.0)
                
                for display in item_summary:
                    item_summary[display]["lacking"] = lacking_map.get(display, 0.0)

            # 3. Draw Summary Table
            y -= 20
            if y < 150:
                c.showPage()
                y = height - 50
            
            c.setFont("Helvetica-Bold", 12)
            c.drawString(40, y, "SUMMARY OF REQUESTS & ISSUANCES")
            y -= 20
            
            c.setFont("Helvetica-Bold", 10)
            c.drawString(40, y, "Item Description")
            c.drawString(450, y, "Total Released")
            c.drawString(580, y, "Total Lacking (Pending)")
            y -= 5
            c.line(40, y, width - 40, y)
            y -= 20
            
            c.setFont("Helvetica", 10)
            # Sort items by name for readability
            for display in sorted(item_summary.keys()):
                if y < 50:
                    c.showPage()
                    y = height - 50
                
                c.drawString(40, y, display)
                c.drawString(450, y, f"{item_summary[display]['released']:.2f}")
                c.drawString(580, y, f"{item_summary[display]['lacking']:.2f}")
                y -= 15

            # --- Transmittal Signatures ---
            y -= 40
            if y < 100:
                c.showPage()
                y = height - 80
            
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y, "Prepared by:")
            c.drawString(320, y, "Checked by/Released by:")
            c.drawString(590, y, "Received by:")
            
            y -= 40
            c.line(50, y, 230, y)
            c.line(320, y, 500, y)
            c.line(590, y, 770, y)
            
            y -= 15
            c.setFont("Helvetica", 9)
            c.drawString(50, y, "Signature over Printed Name / Date")
            c.drawString(320, y, "Signature over Printed Name / Date")
            c.drawString(590, y, "Signature over Printed Name / Date")

            c.save()
            
            QMessageBox.information(self, "Success", f"Issuance log saved as PDF:\n{filename}")
            
            # Auto-open
            try:
                os.startfile(filename)
            except AttributeError:
                if sys.platform == 'darwin': os.system(f'open "{filename}"')
                else: os.system(f'xdg-open "{filename}"')
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {e}")

    def batch_fulfill(self, action='DELIVER'):
        """Processes multiple selected items at once."""
        selected_rows = sorted(list(set(index.row() for index in self.table.selectedIndexes())))
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select one or more rows to process.")
            return
            
        action_msg = "Deliver" if action == 'DELIVER' else "Undo"
        ans = QMessageBox.question(self, f"Confirm Bulk {action_msg}", 
                                 f"Are you sure you want to {action.lower()} {len(selected_rows)} selected items?",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes: return

        success_count = 0
        skip_count = 0
        errors = []
        
        with SessionLocal() as session:
            try:
                for row_idx in selected_rows:
                    try:
                        ri_id = int(self.table.item(row_idx, 7).text())
                        db_ri = session.query(RequestItem).options(
                            joinedload(RequestItem.supply_request),
                            joinedload(RequestItem.item),
                            joinedload(RequestItem.supply_request).joinedload(SupplyRequest.source_location)
                        ).get(ri_id)
                        
                        if not db_ri: continue
                        
                        status_val = db_ri.supply_request.status or "PENDING"
                        is_currently_fulfilled = status_val in ["FULFILLED", "DONE", "DELIVERED"]
                        
                        # Guard: Skip items that already match the target state
                        if action == 'DELIVER' and is_currently_fulfilled:
                            skip_count += 1
                            continue
                        if action == 'UNDO' and not is_currently_fulfilled:
                            skip_count += 1
                            continue
                            
                        # Logic
                        if action == 'UNDO':
                            src_id = db_ri.supply_request.source_location_id
                            stock = session.query(Stock).filter_by(item_id=db_ri.item_id, location_id=src_id).first()
                            if stock:
                                stock.quantity += db_ri.quantity
                            else:
                                session.add(Stock(item_id=db_ri.item_id, location_id=src_id, quantity=db_ri.quantity))
                            db_ri.supply_request.status = "PENDING"
                            success_count += 1
                        else: # DELIVER
                            src_id = db_ri.supply_request.source_location_id
                            stock = session.query(Stock).filter_by(item_id=db_ri.item_id, location_id=src_id).first()
                            curr = stock.quantity if stock else 0.0
                            
                            if curr < db_ri.quantity:
                                skip_count += 1
                                errors.append(f"- {db_ri.item.name} for {db_ri.supply_request.employee.name} (Shortage: {db_ri.quantity - curr:.2f})")
                                continue
                                
                            if stock:
                                stock.quantity -= db_ri.quantity
                            else:
                                session.add(Stock(item_id=db_ri.item_id, location_id=src_id, quantity=-db_ri.quantity))
                            db_ri.supply_request.status = "FULFILLED"
                            success_count += 1
                            
                    except Exception as e:
                        errors.append(f"Row {row_idx+1} Error: {str(e)}")

                session.commit()
                
                summary = f"Processing Complete:\n- {success_count} items processed successfully."
                if skip_count > 0:
                    summary += f"\n- {skip_count} items skipped."
                if errors:
                    summary += "\n\nIssues encountered:\n" + "\n".join(errors[:10])
                    if len(errors) > 10: summary += "\n...and more."
                
                QMessageBox.information(self, "Batch Summary", summary)
                self.load_data()
                if self.parent(): self.parent().refresh_table()
                
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Batch Error", f"Fatal error during batch processing: {str(e)}")

    def fulfill_item(self, ri):
        """Unified toggle fulfillment logic with stock reversal support."""
        with SessionLocal() as session:
            try:
                # Fresh re-fetch
                db_ri = session.query(RequestItem).options(
                    joinedload(RequestItem.supply_request),
                    joinedload(RequestItem.item),
                    joinedload(RequestItem.supply_request).joinedload(SupplyRequest.source_location),
                    joinedload(RequestItem.supply_request).joinedload(SupplyRequest.employee)
                ).get(ri.id)
                
                status_val = db_ri.supply_request.status
                is_undoing = status_val in ["FULFILLED", "DONE", "DELIVERED"]

                if is_undoing:
                    ans = QMessageBox.question(self, "Undo Delivery?", 
                                             f"Restore '{db_ri.item.name}' for {db_ri.supply_request.employee.name} to PENDING?\n\n"
                                             f"This will ADD {db_ri.quantity} units back to {db_ri.supply_request.source_location.name}.",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if ans != QMessageBox.StandardButton.Yes: return

                    # Add stock back
                    src_id = db_ri.supply_request.source_location_id
                    stock = session.query(Stock).filter_by(item_id=db_ri.item_id, location_id=src_id).first()
                    if stock:
                        stock.quantity += db_ri.quantity
                    else:
                        new_stock = Stock(item_id=db_ri.item_id, location_id=src_id, quantity=db_ri.quantity)
                        session.add(new_stock)
                    
                    db_ri.supply_request.status = "PENDING"
                    msg = "Delivery undone. Stock restored."
                else:
                    ans = QMessageBox.question(self, "Confirm Delivery", 
                                             f"Deliver {db_ri.quantity} {db_ri.item.name} to {db_ri.supply_request.employee.name}?\n"
                                             f"Source: {db_ri.supply_request.source_location.name}",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if ans != QMessageBox.StandardButton.Yes: return

                    # Stock Safeguard
                    src_id = db_ri.supply_request.source_location_id
                    item_id = db_ri.item_id
                    stock = session.query(Stock).filter_by(item_id=item_id, location_id=src_id).first()
                    
                    curr = stock.quantity if stock else 0.0
                    if curr < db_ri.quantity:
                        QMessageBox.warning(self, "Insufficient Stock", 
                                           f"Unable to fulfill: {db_ri.item.name} has only {curr:.2f} units available at {db_ri.supply_request.source_location.name}.\n\n"
                                           "Please restock before finalizing this delivery.")
                        return

                    # Process
                    if stock:
                        stock.quantity -= db_ri.quantity
                    else:
                        new_stock = Stock(item_id=item_id, location_id=src_id, quantity=-db_ri.quantity)
                        session.add(new_stock)

                    db_ri.supply_request.status = "FULFILLED"
                    msg = f"Status updated to FULFILLED. {db_ri.quantity} units deducted from inventory."

                session.commit()
                QMessageBox.information(self, "Success", msg)
                self.load_data()
                if self.parent(): self.parent().refresh_table()
                
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to process: {str(e)}")



    def edit_date(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a row to edit.")
            return
            
        row = selected[0].row()
        current_date_str = self.table.item(row, 0).text()
        request_id = int(self.table.item(row, 6).text())
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Request Date")
        l = QVBoxLayout(dialog)
        l.addWidget(QLabel("Select new date for this request:"))
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDate(QDate.fromString(current_date_str, "yyyy-MM-dd"))
        l.addWidget(date_edit)
        
        btns = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
        l.addLayout(btns)
        
        if dialog.exec():
            new_date = date_edit.date()
            new_dt = datetime(new_date.year(), new_date.month(), new_date.day(), 0, 0, 0)
            with SessionLocal() as session:
                req = session.query(SupplyRequest).get(request_id)
                if req:
                    req.request_date = new_dt
                    session.commit()
            
            self.load_data()
            if self.parent():
                self.parent().refresh_table()

class RequestTrackingApp(QWidget):
    def __init__(self, mode="SATELLITE", parent=None):
        super().__init__(parent)
        self.mode = mode
        title = "Satellite Office Request Tracking" if mode == "SATELLITE" else "Main Office Request Manager"
        self.setWindowTitle(title)
        self.setGeometry(100, 100, 1000, 600)
        
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(30, 25, 30, 25)
        self.main_layout.setSpacing(30)
        
        self.setup_input_panel()
        self.setup_table_panel()
        
        # Load initial data
        self.load_dropdowns()
        self.refresh_table()

    def setup_input_panel(self):
        """Creates the form on the left side of the window."""
        self.input_panel = QVBoxLayout()
        
        # Group Box for visual framing
        title = "New Satellite Office Request" if self.mode == "SATELLITE" else "New Main Office Supply Transfer"
        form_group = QGroupBox(title)
        form_layout = QFormLayout()

        # Request Date
        self.req_date_input = QDateEdit()
        self.req_date_input.setCalendarPopup(True)
        self.req_date_input.setDate(QDate.currentDate())
        form_layout.addRow("Request Date:", self.req_date_input)

        # Employee & Department Details
        self.emp_name_input = QComboBox()
        self.emp_name_input.setEditable(True)
        self.emp_name_input.currentTextChanged.connect(self.autofill_employee_details)
        form_layout.addRow("Employee Name:", self.emp_name_input)
        
        self.emp_role_input = QLineEdit()
        form_layout.addRow("Employee Role:", self.emp_role_input)
        
        # Item Details
        self.item_name_input = QComboBox()
        self.item_name_input.setEditable(True)
        form_layout.addRow("Item Requested:", self.item_name_input)
        
        # Strict validation constraint for Quantity (Float > 0)
        self.quantity_input = QLineEdit()
        validator = QDoubleValidator(bottom=0.01)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.quantity_input.setValidator(validator)
        form_layout.addRow("Quantity:", self.quantity_input)
        
        self.area_input = QComboBox()
        self.area_input.setEditable(True)
        form_layout.addRow("Department Area:", self.area_input)
        
        self.shift_input = QLineEdit()
        form_layout.addRow("Shift:", self.shift_input)
        
        self.supervisor_input = QLineEdit()
        form_layout.addRow("Supervisor:", self.supervisor_input)
        
        self.frequency_input = QComboBox()
        self.frequency_input.setEditable(True)
        self.frequency_input.addItems(["1 WEEK", "2 WEEKS", "ONCE A WEEK", "TWICE A WEEK", "1 MONTH", "ONCE A MONTH", "UNTIL DEFECTIVE", "REFILL"])
        form_layout.addRow("Frequency:", self.frequency_input)
        
        self.source_loc_input = QComboBox()
        self.dest_loc_input = QComboBox()
        form_layout.addRow("Fulfillment Source:", self.source_loc_input)
        form_layout.addRow("Requesting Office:", self.dest_loc_input)

        # Buttons
        self.submit_btn = QPushButton("&Submit Request")
        self.submit_btn.setProperty("class", "primary")
        self.submit_btn.clicked.connect(self.submit_request)
        self.submit_btn.setDefault(True)
        
        self.clear_btn = QPushButton("&Clear Form")
        self.clear_btn.clicked.connect(self.clear_form)
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.submit_btn)
        btn_layout.addWidget(self.clear_btn)
        
        form_group.setLayout(form_layout)
        
        self.input_panel.addWidget(form_group)
        self.input_panel.addLayout(btn_layout)
        self.input_panel.addStretch()
        
        self.main_layout.addLayout(self.input_panel, 1) # 1 part width
        
    def setup_table_panel(self):
        """Creates the search bar and results table on the right side."""
        self.table_panel = QVBoxLayout()

        # Search Debounce Timer
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self.run_search)
        
        # Filter Bar Layout
        search_bar = QHBoxLayout()
        search_bar.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find employee, item, or status...")
        self.search_input.textChanged.connect(self.search_timer.start)
        search_bar.addWidget(self.search_input)
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setProperty("class", "secondary")
        self.refresh_btn.clicked.connect(self.refresh_table)
        search_bar.addWidget(self.refresh_btn)

        self.google_sync_btn = QPushButton("📥 Google Form Inbox")
        self.google_sync_btn.setProperty("class", "primary")
        self.google_sync_btn.clicked.connect(self.open_google_inbox)
        search_bar.addWidget(self.google_sync_btn)
        
        self.pending_deliveries_btn = QPushButton("📋 Pending Deliveries / Issuance Log")
        self.pending_deliveries_btn.setProperty("class", "secondary")
        self.pending_deliveries_btn.clicked.connect(self.open_pending_deliveries)
        search_bar.addWidget(self.pending_deliveries_btn)
        
        self.table_panel.addLayout(search_bar)

        bottom_filter_layout = QHBoxLayout()
        bottom_filter_layout.addWidget(QLabel("From:"))
        self.start_date_filter = QDateEdit()
        self.start_date_filter.setCalendarPopup(True)
        self.start_date_filter.setDate(QDate.currentDate().addYears(-1))
        bottom_filter_layout.addWidget(self.start_date_filter)
        
        bottom_filter_layout.addWidget(QLabel("To:"))
        self.end_date_filter = QDateEdit()
        self.end_date_filter.setCalendarPopup(True)
        self.end_date_filter.setDate(QDate.currentDate())
        bottom_filter_layout.addWidget(self.end_date_filter)
        
        self.apply_btn = QPushButton("Apply Filter")
        self.apply_btn.clicked.connect(self.refresh_table)
        bottom_filter_layout.addWidget(self.apply_btn)

        if self.mode == "SATELLITE":
            bottom_filter_layout.addWidget(QLabel("Area:"))
            self.area_filter = QComboBox()
            self.area_filter.addItem("ALL")
            self.area_filter.currentIndexChanged.connect(self.refresh_table)
            bottom_filter_layout.addWidget(self.area_filter)
            

        bottom_filter_layout.addWidget(QLabel("Item:"))
        self.item_filter = QLineEdit()
        self.item_filter.setPlaceholderText("Filter by specific item...")
        self.item_filter.textChanged.connect(self.search_timer.start)
        
        # Setup Completer for Item Search
        self.item_completer = QCompleter()
        self.item_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.item_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.item_filter.setCompleter(self.item_completer)
        
        bottom_filter_layout.addWidget(self.item_filter)

        self.reset_btn = QPushButton("Reset Filter")
        self.reset_btn.clicked.connect(self.reset_filters)
        bottom_filter_layout.addWidget(self.reset_btn)
        
        self.table_panel.addLayout(bottom_filter_layout)
        
        # Clickable hint label
        hint = QLabel("<i>Double-click an employee to view their specific supply requests.</i>")
        hint.setTextFormat(Qt.TextFormat.RichText)
        self.table_panel.addWidget(hint)
        
        self.status_lbl = QLabel("Ready")
        self.table_panel.addWidget(self.status_lbl)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels([
            "ID", "Employee Name", "No. of issuance"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # Make read-only
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.cellDoubleClicked.connect(self.open_employee_details)
        
        self.table_panel.addWidget(self.table)
        
        # Button layout at bottom right
        btn_box = QHBoxLayout()
        
        self.bulk_fulfill_btn = QPushButton("📦 Fulfill Selected Employees")
        self.bulk_fulfill_btn.setProperty("class", "primary")
        self.bulk_fulfill_btn.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.bulk_fulfill_btn.clicked.connect(self.fulfill_selected_employees)
        btn_box.addWidget(self.bulk_fulfill_btn)

        self.bulk_undo_emp_btn = QPushButton("⏪ Undo Fulfillment for Selected")
        self.bulk_undo_emp_btn.setStyleSheet("background-color: #ef6c00; color: white; font-weight: bold;")
        self.bulk_undo_emp_btn.clicked.connect(self.undo_fulfill_selected_employees)
        btn_box.addWidget(self.bulk_undo_emp_btn)
        
        self.delete_emp_btn = QPushButton("Delete Selected Employee")
        self.delete_emp_btn.setProperty("class", "danger")
        self.delete_emp_btn.clicked.connect(self.delete_selected_employee)
        btn_box.addWidget(self.delete_emp_btn)
        
        btn_box.addStretch()
        self.table_panel.addLayout(btn_box)
        
        self.main_layout.addLayout(self.table_panel, 3) # 3 parts width

    def load_dropdowns(self):
        """Pre-fills dropdowns with data already in the database."""
        with SessionLocal() as session:
            locations = session.query(Location).order_by(Location.name).all()
            
            # Refresh source locations
            current_source = self.source_loc_input.currentData()
            self.source_loc_input.blockSignals(True)
            self.source_loc_input.clear()
            for loc in locations:
                self.source_loc_input.addItem(loc.name, loc.id)
            
            idx = self.source_loc_input.findData(current_source)
            if idx >= 0: self.source_loc_input.setCurrentIndex(idx)
            else:
                w_idx = self.source_loc_input.findText("WAREHOUSE")
                if w_idx >= 0: self.source_loc_input.setCurrentIndex(w_idx)
            self.source_loc_input.blockSignals(False)

            # Refresh dest locations
            current_dest = self.dest_loc_input.currentData()
            self.dest_loc_input.blockSignals(True)
            self.dest_loc_input.clear()
            for loc in locations:
                self.dest_loc_input.addItem(loc.name, loc.id)
            
            idx = self.dest_loc_input.findData(current_dest)
            if idx >= 0: self.dest_loc_input.setCurrentIndex(idx)
            else:
                target_loc_name = "MAIN OFFICE" if self.mode == "MAIN_OFFICE" else "SATELLITE OFFICE"
                m_idx = self.dest_loc_input.findText(target_loc_name)
                if m_idx >= 0: self.dest_loc_input.setCurrentIndex(m_idx)
            self.dest_loc_input.blockSignals(False)
            
            # Load item names with descriptions
            items = session.query(Item.id, Item.name, Item.description).all()
            for i in items:
                display = f"{i.name} ({i.description})" if i.description else i.name
                self.item_name_input.addItem(display, {"name": i.name, "description": i.description or ""})
            
            if self.mode == "SATELLITE":
                # Load existing Areas for autocomplete
                distinct_areas = session.query(Department.area_name).distinct().all()
                self.area_input.addItems([a[0] for a in distinct_areas if a[0]])
                
                # Load into filter dropdown too
                self.area_filter.addItems([a[0] for a in distinct_areas if a[0]])

            # Populate Item Completer for Request Section
            completer_items = []
            for i in items:
                display = f"{i.name} ({i.description})" if i.description else i.name
                completer_items.append(display)
            self.item_completer.setModel(QStringListModel(completer_items))

            # Load employee names for autofill
            employees = session.query(Employee.name).order_by(Employee.name).all()
            self.emp_name_input.addItems([e[0] for e in employees])
            self.emp_name_input.setCurrentText("") # Start empty

    def autofill_employee_details(self, name):
        name = name.strip()
        if not name: return

        with SessionLocal() as session:
            emp = session.query(Employee).filter(func.upper(Employee.name) == name.upper()).first()
            if emp:
                # Fetch last request for department info
                last_req = session.query(SupplyRequest).options(joinedload(SupplyRequest.department)).filter_by(employee_id=emp.id).order_by(SupplyRequest.id.desc()).first()
                if last_req and last_req.department:
                    self.emp_role_input.setText(last_req.department.role or emp.role or "")
                    self.supervisor_input.setText(last_req.department.supervisor or "")
                    if self.mode == "SATELLITE":
                        self.area_input.setCurrentText(last_req.department.area_name or "")
                        self.shift_input.setText(last_req.department.shift or "")
                else:
                    self.emp_role_input.setText(emp.role or "")


    def submit_request(self):
        """Handles saving form data into SQLite via SQLAlchemy."""
        emp_name = self.emp_name_input.currentText().strip()
        qty_str = self.quantity_input.text().strip()
        
        # Extract name and description from currentData() or parse currentText()
        item_name = self.item_name_input.currentData()["name"] if self.item_name_input.currentData() else self.item_name_input.currentText().strip().upper()
        item_description = self.item_name_input.currentData()["description"] if self.item_name_input.currentData() else ""
        
        # Collect secondary fields (Conditional)
        role = self.emp_role_input.text().strip()
        area = "N/A"
        shift = "N/A"
        supervisor = "N/A"
        is_refill = False
        freq = "N/A"
        
        area = self.area_input.currentText().strip()
        shift = self.shift_input.text().strip()
        supervisor = self.supervisor_input.text().strip()
        freq = normalize_frequency(self.frequency_input.currentText().strip())

        # Basic GUI-level validation
        if not emp_name or not qty_str or not item_name:
            QMessageBox.warning(self, "Validation Error", "Please fill in all mandatory fields (Name, Item, Quantity).")
            return
            
        try:
            qty_float = float(qty_str)
            if qty_float <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Validation Error", "Quantity must be a positive number greater than 0.")
            return

        with SessionLocal() as session:
            try:
                # 1. Get or Create Employee
                emp = session.query(Employee).filter(func.upper(Employee.name) == emp_name.upper()).first()
                if not emp:
                    emp = Employee(name=emp_name, role=self.emp_role_input.text().strip())
                    session.add(emp)
                    session.flush()
                
                # 2. Get or Create Department
                dept_role = self.emp_role_input.text().strip()
                dept = session.query(Department).filter_by(
                    role=dept_role,
                    area_name=area, 
                    shift=shift,
                    supervisor=supervisor
                ).first()
                if not dept:
                    dept = Department(
                        role=dept_role,
                        area_name=area, 
                        shift=shift, 
                        supervisor=supervisor
                    )
                    session.add(dept)
                    session.flush()

                # 3. Get or Create Item (check if exists by name and description)
                item = session.query(Item).filter_by(name=item_name, description=item_description).first()
                if not item:
                    item = Item(name=item_name, description=item_description)
                    session.add(item)
                    session.flush()

                # 4. Create Supply Request Header
                # Convert QDate to Python datetime (defaulting to midnight)
                selected_qdate = self.req_date_input.date()
                request_dt = datetime(selected_qdate.year(), selected_qdate.month(), selected_qdate.day())

                new_request = SupplyRequest(
                    employee_id=emp.id,
                    department_id=dept.id,
                    request_date=request_dt,
                    source_location_id=self.source_loc_input.currentData(),
                    dest_location_id=self.dest_loc_input.currentData()
                )
                session.add(new_request)
                session.flush()

                # 5. Create Request Item
                req_item = RequestItem(
                    request_id=new_request.id,
                    item_id=item.id,
                    quantity=qty_float,
                    frequency=freq,
                    is_refill_request=is_refill
                )
                session.add(req_item)

                # 6. Set initial status as PENDING (No stock deduction yet)
                new_request.status = "PENDING"
                
                session.commit()
                QMessageBox.information(self, "Success", "Supply request logged (Status: PENDING).\n\nInventory will be deducted only once a custodian marks it as Fulfilled.")
                
                self.reload_autofill_dropdowns()
                self.clear_form(full=False)
                self.refresh_table()
                
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Database Error", f"Failed to save to database:\n{str(e)}")

    def reload_autofill_dropdowns(self):
        """Reloads dynamic dropdowns (like employees and items) to capture newly encoded data."""
        with SessionLocal() as session:
            # Reload employees
            employees = session.query(Employee.name).order_by(Employee.name).all()
            self.emp_name_input.blockSignals(True)
            self.emp_name_input.clear()
            self.emp_name_input.addItems([e[0] for e in employees])
            self.emp_name_input.setCurrentText("")
            self.emp_name_input.blockSignals(False)

            # Reload items
            items = session.query(Item.id, Item.name, Item.description).all()
            self.item_name_input.blockSignals(True)
            self.item_name_input.clear()
            completer_items = []
            for i in items:
                display = f"{i.name} ({i.description})" if i.description else i.name
                self.item_name_input.addItem(display, {"name": i.name, "description": i.description or ""})
                completer_items.append(display)
            self.item_name_input.setCurrentText("")
            self.item_name_input.blockSignals(False)
            
            # Update Item Completer
            self.item_completer.setModel(QStringListModel(completer_items))
            
            distinct_areas = session.query(Department.area_name).distinct().all()
            self.area_input.blockSignals(True)
            self.area_input.clear()
            self.area_input.addItems([a[0] for a in distinct_areas if a[0]])
            self.area_input.setCurrentText("")
            self.area_input.blockSignals(False)
            
            # Also refresh Area Filter, but preserve 'ALL'
            if self.mode == "SATELLITE":
                self.area_filter.blockSignals(True)
                self.area_filter.clear()
                self.area_filter.addItem("ALL")
                self.area_filter.addItems([a[0] for a in distinct_areas if a[0]])
                self.area_filter.blockSignals(False)

    def refresh_table(self):
        """Loads a list of distinct employees and their request count matching the date, area, item, and search filters."""
        self.table.setRowCount(0)
        
        # Get Filters (Conditional)
        search_text = self.search_input.text().lower().strip()
        item_search = self.item_filter.text().lower().strip()
        start_qdate = self.start_date_filter.date()
        end_qdate = self.end_date_filter.date()
        
        start_dt = datetime(start_qdate.year(), start_qdate.month(), start_qdate.day(), 0, 0, 0)
        end_dt = datetime(end_qdate.year(), end_qdate.month(), end_qdate.day(), 23, 59, 59)
        
        area_filter = None
        if self.mode == "SATELLITE":
            area_filter = self.area_filter.currentText()

        with SessionLocal() as session:
            # Main query for employees
            query = session.query(
                Employee.id,
                Employee.name,
                Employee.role
            ).outerjoin(SupplyRequest, Employee.id == SupplyRequest.employee_id) \
             .outerjoin(Department, SupplyRequest.department_id == Department.id) \
             .outerjoin(RequestItem, SupplyRequest.id == RequestItem.request_id) \
             .outerjoin(Item, RequestItem.item_id == Item.id)
            
            # Apply Item Search if provided
            if item_search:
                query = query.filter(
                    (Item.name.ilike(f"%{item_search}%")) | 
                    (Item.description.ilike(f"%{item_search}%")) |
                    ((Item.name + " (" + func.coalesce(Item.description, "") + ")").ilike(f"%{item_search}%"))
                )

            # Apply Main Search (Employee Name or Role)
            if search_text:
                query = query.filter(
                    (Employee.name.ilike(f"%{search_text}%")) | 
                    (Employee.role.ilike(f"%{search_text}%"))
                )

            # Global Search Override: If there's no search text, respect Area filter
            if not search_text and area_filter and area_filter != "ALL":
                query = query.filter(Department.area_name == area_filter)

            # Date Range Filter (only for requests in this period)
            query = query.filter(
                (SupplyRequest.request_date >= start_dt) & 
                (SupplyRequest.request_date <= end_dt)
            )

            employees = query.group_by(Employee.id).order_by(Employee.name).all()

            row_idx = 0
            target_loc_name = "MAIN OFFICE" if self.mode == "MAIN_OFFICE" else "SATELLITE OFFICE"
            
            for emp in employees:
                # 1. Fetch latest request info including location
                latest_req = session.query(SupplyRequest).options(
                    joinedload(SupplyRequest.dest_location),
                    joinedload(SupplyRequest.department)
                ).filter_by(employee_id=emp.id).order_by(SupplyRequest.request_date.desc()).first()
                
                # Office View Isolation Filter:
                if self.mode != "UNIFIED" and latest_req and latest_req.dest_location:
                    if latest_req.dest_location.name != target_loc_name:
                        continue

                # Fetch count of ALL requests in the period (respecting item search)
                count_query = session.query(func.count(SupplyRequest.id)).join(RequestItem).join(Item).filter(
                    SupplyRequest.employee_id == emp.id,
                    SupplyRequest.request_date >= start_dt,
                    SupplyRequest.request_date <= end_dt
                )
                if item_search:
                    count_query = count_query.filter(
                        (Item.name.ilike(f"%{item_search}%")) | 
                        (Item.description.ilike(f"%{item_search}%")) |
                        ((Item.name + " (" + func.coalesce(Item.description, "") + ")").ilike(f"%{item_search}%"))
                    )
                
                total_in_period = count_query.scalar() or 0
                if total_in_period == 0:
                    continue
                
                # Insert row
                self.table.insertRow(row_idx)
                self.table.setItem(row_idx, 0, QTableWidgetItem(str(emp.id)))
                self.table.setItem(row_idx, 1, QTableWidgetItem(emp.name))
                
                # Fetch count of fulfilled requests for No. of issuance (respecting item search)
                iss_query = session.query(func.count(SupplyRequest.id)).join(RequestItem).join(Item).filter(
                    SupplyRequest.employee_id == emp.id,
                    SupplyRequest.status.in_(["FULFILLED", "DONE", "DELIVERED"]),
                    SupplyRequest.request_date >= start_dt,
                    SupplyRequest.request_date <= end_dt
                )
                if item_search:
                    iss_query = iss_query.filter(
                        (Item.name.ilike(f"%{item_search}%")) | 
                        (Item.description.ilike(f"%{item_search}%")) |
                        ((Item.name + " (" + func.coalesce(Item.description, "") + ")").ilike(f"%{item_search}%"))
                    )
                
                issuance_count = iss_query.scalar() or 0
                self.table.setItem(row_idx, 2, QTableWidgetItem(str(issuance_count)))
                
                row_idx += 1
        self.filter_table()
                
    def run_search(self):
        """Triggers both database refresh (dates) and local filtering (text)."""
        self.refresh_table()

    def reset_filters(self):
        """Reset search and date filters to defaults."""
        self.search_input.clear()
        self.start_date_filter.setDate(QDate.currentDate().addYears(-1))
        self.end_date_filter.setDate(QDate.currentDate())
        if self.mode == "SATELLITE":
            self.area_filter.setCurrentIndex(0)
        self.item_filter.clear()
        self.refresh_table()

    def open_employee_details(self, row, column):
        """Opens a dialog showing the specific items this employee requested."""
        emp_id = int(self.table.item(row, 0).text())
        emp_name = self.table.item(row, 1).text()
        
        dialog = EmployeeDetailsDialog(employee_id=emp_id, employee_name=emp_name, mode=self.mode, parent=self)
        dialog.exec()


    def open_pending_deliveries(self):
        """Opens the custodian dashboard for fulfilling requests."""
        dialog = PendingRequestsDialog(mode=self.mode, parent=self)
        dialog.exec()

    def open_google_inbox(self):
        """Opens the inbox to review Google Form submissions."""
        dialog = GoogleSyncInboxDialog(mode=self.mode, parent=self)
        dialog.exec()
        self.refresh_table()

    def fulfill_selected_employees(self):
        """Finds all PENDING requests for selected employees matching current filters and fulfills them if stock is available."""
        selected_rows = sorted(list(set(index.row() for index in self.table.selectedIndexes())))
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select one or more employees.")
            return
            
        emp_ids = []
        for row in selected_rows:
            emp_ids.append(int(self.table.item(row, 0).text()))
            
        # Capture current filters to restrict fulfillment to what the user actually sees
        item_search = self.item_filter.text().lower().strip()
        start_qdate = self.start_date_filter.date()
        end_qdate = self.end_date_filter.date()
        start_dt = datetime(start_qdate.year(), start_qdate.month(), start_qdate.day(), 0, 0, 0)
        end_dt = datetime(end_qdate.year(), end_qdate.month(), end_qdate.day(), 23, 59, 59)
            
        ans = QMessageBox.question(self, "Bulk Fulfillment", 
                                 f"Attempt to fulfill pending requests for {len(emp_ids)} selected employees\n(matching your current date/item filters)?",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes: return

        processed_count = 0
        skip_count = 0
        errors = []
        
        target_loc_name = "MAIN OFFICE" if self.mode == "MAIN_OFFICE" else "SATELLITE OFFICE"
        
        with SessionLocal() as session:
            try:
                # Find all PENDING request items for these employees destined for this office AND matching filters
                query = session.query(RequestItem).join(SupplyRequest).join(Location, SupplyRequest.dest_location_id == Location.id).join(Item).filter(
                    SupplyRequest.employee_id.in_(emp_ids),
                    SupplyRequest.status.in_([None, "PENDING"]),
                    Location.name == target_loc_name,
                    SupplyRequest.request_date >= start_dt,
                    SupplyRequest.request_date <= end_dt
                )
                
                if item_search:
                    query = query.filter(
                        (Item.name.ilike(f"%{item_search}%")) | 
                        (Item.description.ilike(f"%{item_search}%")) |
                        ((Item.name + " (" + func.coalesce(Item.description, "") + ")").ilike(f"%{item_search}%"))
                    )
                    
                items_to_process = query.all()
                
                if not items_to_process:
                    QMessageBox.information(self, "No Pending Work", "No pending requests found for the selected employees.")
                    return

                for ri in items_to_process:
                    src_id = ri.supply_request.source_location_id
                    stock = session.query(Stock).filter_by(item_id=ri.item_id, location_id=src_id).first()
                    curr = stock.quantity if stock else 0.0
                    
                    if curr < ri.quantity:
                        skip_count += 1
                        errors.append(f"- {ri.item.name} for {ri.supply_request.employee.name} (Shortage: {ri.quantity - curr:.2f})")
                        continue
                        
                    if stock:
                        stock.quantity -= ri.quantity
                    else:
                        session.add(Stock(item_id=ri.item_id, location_id=src_id, quantity=-ri.quantity))
                    
                    ri.supply_request.status = "FULFILLED"
                    processed_count += 1
                
                session.commit()
                
                summary = f"Bulk Fulfillment Results:\n- {processed_count} requests fulfilled."
                if skip_count > 0:
                    summary += f"\n- {skip_count} requests skipped due to stock/errors."
                if errors:
                    summary += "\n\nStock Conflicts:\n" + "\n".join(errors[:10])
                    if len(errors) > 10: summary += "\n...and more."
                
                QMessageBox.information(self, "Bulk Fulfillment Summary", summary)
                self.refresh_table()
                
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to perform bulk fulfillment: {str(e)}")

    def undo_fulfill_selected_employees(self):
        """Finds all FULFILLED/DONE requests for selected employees matching current filters and reverts them to PENDING, restoring stock."""
        selected_rows = sorted(list(set(index.row() for index in self.table.selectedIndexes())))
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select one or more employees.")
            return
            
        emp_ids = []
        for row in selected_rows:
            emp_ids.append(int(self.table.item(row, 0).text()))
            
        item_search = self.item_filter.text().lower().strip()
        start_qdate = self.start_date_filter.date()
        end_qdate = self.end_date_filter.date()
        start_dt = datetime(start_qdate.year(), start_qdate.month(), start_qdate.day(), 0, 0, 0)
        end_dt = datetime(end_qdate.year(), end_qdate.month(), end_qdate.day(), 23, 59, 59)
            
        ans = QMessageBox.question(self, "Bulk Undo Fulfillment", 
                                 f"Revert fulfilled requests for {len(emp_ids)} selected employees\n(matching your current date/item filters) to PENDING?\nStock will be restored.",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes: return

        processed_count = 0
        skip_count = 0
        
        target_loc_name = "MAIN OFFICE" if self.mode == "MAIN_OFFICE" else "SATELLITE OFFICE"
        
        with SessionLocal() as session:
            try:
                # Find all FULFILLED/DONE/DELIVERED request items for these employees destined for this office AND matching filters
                query = session.query(RequestItem).join(SupplyRequest).join(Location, SupplyRequest.dest_location_id == Location.id).join(Item).filter(
                    SupplyRequest.employee_id.in_(emp_ids),
                    SupplyRequest.status.in_(["FULFILLED", "DONE", "DELIVERED"]),
                    Location.name == target_loc_name,
                    SupplyRequest.request_date >= start_dt,
                    SupplyRequest.request_date <= end_dt
                )
                
                if item_search:
                    query = query.filter(
                        (Item.name.ilike(f"%{item_search}%")) | 
                        (Item.description.ilike(f"%{item_search}%")) |
                        ((Item.name + " (" + func.coalesce(Item.description, "") + ")").ilike(f"%{item_search}%"))
                    )
                    
                items_to_undo = query.all()
                
                if not items_to_undo:
                    QMessageBox.information(self, "No Work Found", "No fulfilled requests found for the selected employees.")
                    return

                for ri in items_to_undo:
                    # Restore Stock
                    src_id = ri.supply_request.source_location_id
                    stock = session.query(Stock).filter_by(item_id=ri.item_id, location_id=src_id).first()
                    if stock:
                        stock.quantity += ri.quantity
                    else:
                        session.add(Stock(item_id=ri.item_id, location_id=src_id, quantity=ri.quantity))
                    
                    ri.supply_request.status = "PENDING"
                    processed_count += 1
                
                session.commit()
                
                QMessageBox.information(self, "Bulk Undo Summary", f"Successfully reverted {processed_count} fulfillments and restored stock.")
                self.refresh_table()
                
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to perform bulk undo: {str(e)}")

    def delete_selected_employee(self):
        """Removes selected employees and all their history after bulk confirmation."""
        # Get unique rows from selected items
        selected_rows = sorted(list(set(item.row() for item in self.table.selectedItems())), reverse=True)
        
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select one or more employees to delete.")
            return
            
        employees_to_delete = []
        for row in selected_rows:
            emp_id = int(self.table.item(row, 0).text())
            emp_name = self.table.item(row, 1).text()
            employees_to_delete.append((emp_id, emp_name))

        count = len(employees_to_delete)
        if count == 1:
            msg = f"Are you sure you want to delete '{employees_to_delete[0][1]}'?"
        else:
            names = ", ".join([e[1] for e in employees_to_delete[:5]])
            if count > 5: names += "..."
            msg = f"Are you sure you want to delete {count} selected employees?\n({names})"

        msg += "\n\nWARNING: This will permanently delete their entire request history."
        
        ans = QMessageBox.question(self, "Confirm Bulk Deletion", 
                                 msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if ans == QMessageBox.StandardButton.Yes:
            with SessionLocal() as session:
                try:
                    for emp_id, emp_name in employees_to_delete:
                        emp = session.query(Employee).get(emp_id)
                        if emp:
                            session.delete(emp)
                    
                    session.commit()
                    self.refresh_table()
                    self.load_dropdowns()
                    QMessageBox.information(self, "Deleted", f"Successfully deleted {count} employees and their records.")
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Error", f"Failed to perform bulk deletion: {str(e)}")

    def clear_form(self, full=True):
        if full:
            self.req_date_input.setDate(QDate.currentDate())
            self.emp_name_input.setCurrentText("")
            self.emp_role_input.clear()
        
        self.item_name_input.setCurrentText("")
        self.quantity_input.clear()
        
        self.shift_input.clear()
        self.supervisor_input.clear()

    def filter_table(self):
        """Hides or shows rows based on search text."""
        search_text = self.search_input.text().lower().strip()
        visible_count = 0
        for row in range(self.table.rowCount()):
            match = False
            if not search_text:
                match = True
            else:
                for col in range(self.table.columnCount()):
                    item_obj = self.table.item(row, col)
                    if item_obj and search_text in item_obj.text().lower():
                        match = True
                        break
            
            self.table.setRowHidden(row, not match)
            if match:
                visible_count += 1
                
        # UX: Update status label
        if visible_count == 0:
            self.status_lbl.setText("No employees found matching your search/filters.")
        else:
            self.status_lbl.setText(f"Showing {visible_count} employees with issuance history")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Optional: Set a clean, modern stylesheet if desired
    app.setStyle("Fusion")
    
    window = RequestTrackingApp()
    window.show()
    sys.exit(app.exec())
