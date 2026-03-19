import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton, QTableWidget, 
                             QTableWidgetItem, QMessageBox, QHeaderView, QGroupBox, QFormLayout, 
                             QDialog, QDateEdit, QListWidget, QScrollArea, QFrame, QProgressBar,
                             QDialogButtonBox)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIntValidator, QDoubleValidator, QColor, QBrush

# Import backend logic
from database import (SessionLocal, Employee, SupplyRequest, Item, Department, 
                      RequestItem, Stock, Location, parse_frequency)
from exporter import export_to_excel
from form_generator import generate_blank_form, generate_populated_report, generate_consumption_report
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from datetime import datetime, timedelta

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
        
        self.name_input = QLineEdit()
        self.role_input = QLineEdit()
        self.area_input = QLineEdit()
        self.shift_input = QLineEdit()
        self.supervisor_input = QLineEdit()
        self.item_name_input = QComboBox()
        self.item_name_input.setEditable(True)
        
        self.qty_input = QLineEdit()
        self.qty_input.setValidator(QDoubleValidator(0.1, 999.0, 2))
        
        self.is_refill_cb = QCheckBox("Is this a refill?")
        self.frequency_input = QComboBox()
        self.frequency_input.setEditable(True)
        self.frequency_input.addItems(["1 WEEK", "2 WEEKS", "1 MONTH", "UNTIL DEFECTIVE", "REFILL"])
        
        self.source_loc_input = QComboBox()
        self.dest_loc_input = QComboBox()
        
        form.addRow("Request Date:", self.date_edit)
        form.addRow("Employee Name:", self.name_input)
        
        if self.mode == "SATELLITE":
            form.addRow("Employee Role:", self.role_input)
            form.addRow("Area/Department:", self.area_input)
            form.addRow("Shift:", self.shift_input)
            form.addRow("Supervisor:", self.supervisor_input)
            
        form.addRow("Item Name:", self.item_name_input)
        form.addRow("Quantity:", self.qty_input)
        
        if self.mode == "SATELLITE":
            form.addRow("Refill Request:", self.is_refill_cb)
            form.addRow("Frequency:", self.frequency_input)
            
        form.addRow("Fulfillment Source:", self.source_loc_input)
        form.addRow("Requesting Office:", self.dest_loc_input)
        
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        save_btn = QPushButton("Save Changes")
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
            items = session.query(Item.name).order_by(Item.name).all()
            self.item_name_input.addItems([i[0] for i in items])
            
            locations = session.query(Location).all()
            for loc in locations:
                self.source_loc_input.addItem(loc.name, loc.id)
                self.dest_loc_input.addItem(loc.name, loc.id)
            
            # Prepopulate area if adding for specific employee
            if self.employee_id and not self.request_item_id:
                emp = session.query(Employee).get(self.employee_id)
                if emp:
                    self.name_input.setText(emp.name)
                    self.role_input.setText(emp.role or "")
                
                last_req = session.query(SupplyRequest).filter_by(employee_id=self.employee_id).order_by(SupplyRequest.id.desc()).first()
                if last_req and self.mode == "SATELLITE":
                    if last_req.department:
                        self.area_input.setText(last_req.department.area_name or "")
                        self.shift_input.setText(last_req.department.shift or "")
                        self.supervisor_input.setText(last_req.department.supervisor or "")

    def load_current_data(self):
        with SessionLocal() as session:
            req = session.query(RequestItem).options(
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.department),
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.source_location),
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.dest_location),
                joinedload(RequestItem.item)
            ).get(self.request_item_id)
            
            if req:
                self.name_input.setText(req.supply_request.employee.name)
                self.role_input.setText(req.supply_request.employee.role or "")
                rd = req.supply_request.request_date
                self.date_edit.setDate(QDate(rd.year, rd.month, rd.day))
                self.item_name_input.setCurrentText(req.item.name)
                self.qty_input.setText(str(req.quantity))
                
                if self.mode == "SATELLITE":
                    if req.supply_request.department:
                        self.area_input.setText(req.supply_request.department.area_name or "")
                        self.shift_input.setText(req.supply_request.department.shift or "")
                        self.supervisor_input.setText(req.supply_request.department.supervisor or "")
                    self.is_refill_cb.setChecked(req.is_refill_request)
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
            "name": self.name_input.text().strip(),
            "role": self.role_input.text().strip(),
            "date": self.date_edit.date().toPyDate(),
            "item": self.item_name_input.currentText().strip().upper(),
            "qty": float(self.qty_input.text() or 0),
            "source_loc_id": self.source_loc_input.currentData(),
            "dest_loc_id": self.dest_loc_input.currentData(),
            "area": "N/A",
            "shift": "N/A",
            "supervisor": "N/A",
            "refill": False,
            "freq": "N/A"
        }
        
        if self.mode == "SATELLITE":
            data["area"] = self.area_input.text().strip()
            data["shift"] = self.shift_input.text().strip()
            data["supervisor"] = self.supervisor_input.text().strip()
            data["refill"] = self.is_refill_cb.isChecked()
            data["freq"] = self.frequency_input.currentText().strip()
            
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
        
        header_labels = [self.label_first, self.label_total]
        if self.mode == "SATELLITE":
            header_labels = [self.label_role, self.label_area, self.label_shift, self.label_super] + header_labels
        
        for lbl in header_labels:
            lbl.setTextFormat(Qt.TextFormat.RichText)
            self.info_layout.addWidget(lbl)
            
        layout.addWidget(self.info_box)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Date", "Area", "Shift", "Item Requested", "Qty", "Refill?", "Frequency", "Req ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(7, True)
        self.table.setColumnHidden(7, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems) # Select cells, not just rows
        self.table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
        self.table.itemChanged.connect(self.save_cell_edit)
        layout.addWidget(self.table)
        
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add New Item")
        self.add_btn.clicked.connect(self.add_new_request_item)
        self.add_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        

        self.edit_btn = QPushButton("Edit Selected Request")
        self.edit_btn.clicked.connect(self.edit_selected_request)
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.delete_selected_request)
        self.delete_btn.setStyleSheet("color: #c0392b; font-weight: bold;")
        
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

        self.print_btn = QPushButton("Export/Print History to Excel")
        self.print_btn.clicked.connect(self.run_print_history)
        layout.addWidget(self.print_btn)
        
        self.load_data()

    def load_data(self):
        self.table.blockSignals(True) # Prevent save_cell_edit from firing during load
        with SessionLocal() as session:
            # Fetch Employee Metadata first
            employee = session.query(Employee).options(
                joinedload(Employee.requests).joinedload(SupplyRequest.department)
            ).filter(Employee.id == self.employee_id).first()
            
            if employee:
                self.label_role.setText(f"<b>Role:</b> {employee.role or 'N/A'}")
                # Get the most common or latest department for them
                if employee.requests and self.mode == "SATELLITE":
                    latest_dept = employee.requests[-1].department
                    self.label_area.setText(f"<b>Area:</b> {latest_dept.area_name or 'N/A'}")
                    self.label_shift.setText(f"<b>Shift:</b> {latest_dept.shift or 'N/A'}")
                    self.label_super.setText(f"<b>Supervisor:</b> {latest_dept.supervisor or 'N/A'}")

            requests = session.query(RequestItem).join(SupplyRequest).filter(
                SupplyRequest.employee_id == self.employee_id
            ).options(
                joinedload(RequestItem.item),
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.department)
            ).order_by(RequestItem.id.desc()).all()
            
            # Pre-fetch Warehouse ID and Stock Levels for highlighting
            warehouse_id = session.query(Location.id).filter_by(name="WAREHOUSE").scalar()
            warehouse_stocks = {}
            if warehouse_id:
                stocks = session.query(Stock).filter_by(location_id=warehouse_id).all()
                warehouse_stocks = {s.item_id: s.quantity for s in stocks}
            
            # Fetch Warehouse Stock for all requested items to check status
            referenced_item_ids = [r.item_id for r in requests]
            if warehouse_id:
                # warehouse_stocks mapping: {item_id: quantity}
                # If item_id is not in warehouse_stocks, it truly doesn't exist in the Warehouse storage.
                pass
            
            # Master Item Check: Does it have ANY database record in the Warehouse?
            all_master_items = session.query(Item.name).order_by(Item.name).all()
            all_item_names = [i[0] for i in all_master_items]

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
                area_name = req.supply_request.department.area_name or "Unknown"
                shift_val = req.supply_request.department.shift or ""
                
                # Determine Highlight Color
                # Determine Highlight Color based on Warehouse Status
                # Red: Item NOT found in Warehouse system (no stock record for WAREHOUSE)
                # Orange: Item found in Warehouse but Out of Stock (Qty <= 0)
                # Green: Item found in Warehouse and In Stock (Qty > 0)
                bg_color = None
                
                # Check if item has a stock entry for the warehouse
                if req.item_id not in warehouse_stocks:
                    bg_color = QColor("#ffcdd2") # Light Red (Non-existing in Warehouse)
                else:
                    qty = warehouse_stocks.get(req.item_id, 0.0)
                    if qty <= 0:
                        bg_color = QColor("#ffe0b2") # Light Orange (Out of Stock)
                    else:
                        bg_color = QColor("#c8e6c9") # Light Green (In Stock)

                self.table.setItem(row_idx, 0, QTableWidgetItem(date_str))
                self.table.setItem(row_idx, 1, QTableWidgetItem(area_name))
                self.table.setItem(row_idx, 2, QTableWidgetItem(shift_val))
                
                item_name_text = req.item.name
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
                    
                    self.table.setCellWidget(row_idx, 3, combo)
                else:
                    item_cell = QTableWidgetItem(item_name_text)
                    if bg_color:
                        item_cell.setBackground(QBrush(bg_color))
                    self.table.setItem(row_idx, 3, item_cell)
                self.table.setItem(row_idx, 4, QTableWidgetItem(str(req.quantity)))
                self.table.setItem(row_idx, 5, QTableWidgetItem("Yes" if req.is_refill_request else "No"))
                self.table.setItem(row_idx, 6, QTableWidgetItem(req.frequency or ""))
                
                self.table.setItem(row_idx, 7, QTableWidgetItem(str(req.id))) # Store RequestItem ID here
                
                # Make non-editable columns read-only
                for col in [0, 3, 5, 7]: 
                    it = self.table.item(row_idx, col)
                    if it: it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.table.blockSignals(False)

    def resolve_item_mismatch(self, request_item_id, combo_box, selected_name=None):
        """Updates the RequestItem's linked item when a suggestion is picked."""
        if selected_name is None:
            selected_name = combo_box.currentText()
            
        selected_name = selected_name.strip()
        if "🔍 NOT FOUND" in selected_name: return # Still not found
        
        with SessionLocal() as session:
            try:
                # 1. Fetch the chosen item from master list
                item_obj = session.query(Item).filter(func.upper(Item.name) == selected_name.upper()).first()
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
        
        # Get the ID of the RequestItem (stored in hidden col 7)
        id_item = self.table.item(row, 7)
        if not id_item: return
        request_item_id = int(id_item.text())

        with SessionLocal() as session:
            try:
                req_item = session.query(RequestItem).options(
                    joinedload(RequestItem.supply_request).joinedload(SupplyRequest.department)
                ).get(request_item_id)
                
                if not req_item: return

                if col == 1: # Area
                    # Update the department name for this request
                    req_item.supply_request.department.area_name = new_val
                elif col == 2: # Shift
                    req_item.supply_request.department.shift = new_val
                elif col == 4: # Qty
                    try:
                        req_item.quantity = float(new_val)
                    except ValueError:
                        QMessageBox.warning(self, "Invalid Input", "Quantity must be a number.")
                        self.load_data()
                        return
                elif col == 6: # Frequency
                    req_item.frequency = new_val
                
                session.commit()
                # Optional visual feedback or just stay quiet
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Database Error", f"Failed to save change:\n{str(e)}")
                self.load_data()


    def run_print_history(self):
        """Generates a professional Excel report for this specific employee."""
        with SessionLocal() as session:
            # Query all items for this employee to get metadata (role, area, etc.)
            requests = session.query(RequestItem).join(SupplyRequest).filter(
                SupplyRequest.employee_id == self.employee_id
            ).options(
                joinedload(RequestItem.item),
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.employee),
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.department)
            ).order_by(RequestItem.id.desc()).all()

            if not requests:
                QMessageBox.warning(self, "No Data", "No history found for this employee.")
                return

            # Extract metadata from the most recent request
            latest = requests[0]
            role = latest.supply_request.employee.role or ""
            area = latest.supply_request.department.area_name or "Unknown"
            shift = latest.supply_request.department.shift or ""
            supervisor = latest.supply_request.department.supervisor or ""

            # Format data for the generator
            data_rows = []
            for r in requests:
                data_rows.append((
                    r.supply_request.request_date.strftime("%Y-%m-%d"),
                    r.item.name,
                    r.quantity,
                    "Yes" if r.is_refill_request else "No",
                    r.frequency or ""
                ))

            try:
                filename = generate_populated_report(
                    self.windowTitle().replace("Request History: ", ""),
                    role, area, shift, supervisor, data_rows
                )
                QMessageBox.information(self, "Success", f"Professional report generated: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to generate report:\n{str(e)}")

    def edit_selected_request(self):
        """Opens a comprehensive dialog to edit all fields of the selected request."""
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a request to edit.")
            return
            
        row = selected_items[0].row()
        request_item_id = int(self.table.item(row, 7).text())
        
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
                        
                        req_item.supply_request.employee.role = data["role"]
                        
                        # Update Supply Request (Date & Locations)
                        d = data["date"]
                        new_dt = datetime(d.year, d.month, d.day)
                        req_item.supply_request.request_date = new_dt
                        req_item.supply_request.source_location_id = data["source_loc_id"]
                        req_item.supply_request.dest_location_id = data["dest_loc_id"]
                        
                        # Find or Create Department (Isolation Fix)
                        new_dept = session.query(Department).filter_by(
                            area_name=data["area"],
                            shift=data["shift"],
                            supervisor=data["supervisor"]
                        ).first()
                        
                        if not new_dept:
                            new_dept = Department(
                                area_name=data["area"],
                                shift=data["shift"],
                                supervisor=data["supervisor"]
                            )
                            session.add(new_dept)
                            session.flush()
                        
                        req_item.supply_request.department = new_dept
                        
                        # Update Item (check if exists)
                        item_obj = session.query(Item).filter(Item.name == data["item"]).first()
                        if not item_obj:
                            item_obj = Item(name=data["item"])
                            session.add(item_obj)
                            session.flush()
                        
                        req_item.item_id = item_obj.id
                        req_item.quantity = data["qty"]
                        req_item.is_refill_request = data["refill"]
                        req_item.frequency = data["freq"]
                        
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
                    emp = session.query(Employee).filter_by(name=new_name).first()
                    if not emp:
                        emp = Employee(name=new_name, role=data["role"])
                        session.add(emp)
                        session.flush()
                    else:
                        emp.role = data["role"]
                    
                    # 2. Get or Create Department
                    dept = session.query(Department).filter_by(
                        area_name=data["area"],
                        shift=data["shift"],
                        supervisor=data["supervisor"]
                    ).first()
                    
                    if not dept:
                        dept = Department(
                            area_name=data["area"],
                            shift=data["shift"],
                            supervisor=data["supervisor"]
                        )
                        session.add(dept)
                        session.flush()

                    # 2. Get or Create Item
                    item_obj = session.query(Item).filter(Item.name == data["item"]).first()
                    if not item_obj:
                        item_obj = Item(name=data["item"])
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
                        is_refill_request=data["refill"],
                        frequency=data["freq"]
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
                        req_item_id = int(self.table.item(row, 7).text())
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

class UsageCard(QFrame):
    """A custom widget to visually display consumption stats for a single item."""
    def __init__(self, item_name, avg_days, weekly, yearly, status, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            UsageCard {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 10px;
                margin-bottom: 8px;
            }
            UsageCard:hover { border: 1px solid #1F4E78; background-color: #f0f7ff; }
            QLabel#ItemTitle { font-weight: bold; font-size: 14px; color: #1F4E78; }
            QLabel#StatLabel { color: #7f8c8d; font-size: 11px; text-transform: uppercase; }
            QLabel#StatValue { font-weight: bold; font-size: 14px; color: #2c3e50; }
        """)
        
        layout = QVBoxLayout(self)
        
        # Header: Name and Status
        header = QHBoxLayout()
        title = QLabel(item_name)
        title.setObjectName("ItemTitle")
        header.addWidget(title)
        
        status_lbl = QLabel(status)
        color = "#e74c3c" if "High" in status else "#2ecc71" if "Normal" in status else "#3498db"
        status_lbl.setStyleSheet(f"font-weight: bold; color: {color};")
        header.addStretch()
        header.addWidget(status_lbl)
        layout.addLayout(header)
        
        # Speed Indicator (Progress Bar)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        
        if avg_days:
            val = max(0, min(100, int((30 - avg_days) / 30 * 100)))
            self.progress.setValue(val)
            color = "#e74c3c" if avg_days < 7 else "#3498db" if avg_days < 30 else "#2ecc71"
            self.progress.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }}")
        else:
            self.progress.setValue(0)
        layout.addWidget(self.progress)
        
        # Stats Grid
        stats = QHBoxLayout()
        def add_stat(label, value):
            vbox = QVBoxLayout()
            vbox.setSpacing(2)
            l = QLabel(label); l.setObjectName("StatLabel")
            v = QLabel(value); v.setObjectName("StatValue")
            vbox.addWidget(l); vbox.addWidget(v)
            stats.addLayout(vbox)
        
        add_stat("Avg Gap", f"{avg_days:.1f} Days" if avg_days else "N/A")
        stats.addStretch()
        add_stat("Weekly", weekly)
        stats.addStretch()
        add_stat("Yearly", yearly)
        layout.addLayout(stats)

class ConsumptionReportDialog(QDialog):
    def __init__(self, mode="SATELLITE", parent=None):
        super().__init__(parent)
        self.mode = mode
        title_text = "Total Requested Log" if mode == "MAIN_OFFICE" else "Supply Consumption & Usage Analysis"
        self.setWindowTitle(title_text)
        self.setMinimumSize(950, 700)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        
        title_box = QVBoxLayout()
        header_text = "Total Requested Log" if mode == "MAIN_OFFICE" else "Supply Consumption Dashboard"
        title = QLabel(header_text)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1F4E78;")
        title_box.addWidget(title)
        subtitle_text = "View detailed request history for office employees." if mode == "MAIN_OFFICE" else "Select an employee on the left to view their visual consumption analytics."
        subtitle = QLabel(subtitle_text)
        subtitle.setStyleSheet("color: #666; font-size: 13px;")
        title_box.addWidget(subtitle)
        self.main_layout.addLayout(title_box)

        # Split Pane
        self.split_pane = QHBoxLayout()
        # LEFT: Employee Browser
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("<b>Browse Employees</b>"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name...")
        self.search_input.textChanged.connect(self.filter_employees)
        left_panel.addWidget(self.search_input)
        self.emp_list = QListWidget()
        self.emp_list.itemClicked.connect(self.on_employee_selected)
        left_panel.addWidget(self.emp_list)
        self.split_pane.addLayout(left_panel, 1)
        
        # RIGHT: Analytics Panel
        right_panel = QVBoxLayout()
        panel_header = "Detailed Request Log" if self.mode == "MAIN_OFFICE" else "Analytical Breakdown"
        right_panel.addWidget(QLabel(f"<b>{panel_header}</b>"))
        
        if self.mode == "MAIN_OFFICE":
            self.log_table = QTableWidget()
            self.log_table.setColumnCount(3)
            self.log_table.setHorizontalHeaderLabels(["Date", "Item Name", "Quantity"])
            self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            right_panel.addWidget(self.log_table)
        else:
            self.scroll = QScrollArea()
            self.scroll.setWidgetResizable(True)
            self.dash_content = QWidget()
            self.dash_content.setStyleSheet("background-color: #f4f7f9; border-radius: 10px;")
            self.dash_layout = QVBoxLayout(self.dash_content)
            self.dash_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.placeholder = QLabel("\n\n\n\n\nSelect an employee to view details.")
            self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.dash_layout.addWidget(self.placeholder)
            self.scroll.setWidget(self.dash_content)
            right_panel.addWidget(self.scroll)
            
        self.split_pane.addLayout(right_panel, 3)
        self.main_layout.addLayout(self.split_pane)

        # Bottom Actions
        footer = QHBoxLayout()
        self.print_btn = QPushButton("Export Current Summary to Excel")
        self.print_btn.setEnabled(False) 
        self.print_btn.clicked.connect(self.run_export)
        footer.addStretch()
        footer.addWidget(self.print_btn)
        self.main_layout.addLayout(footer)

        self.load_data_stats()

    def load_data_stats(self):
        def parse_freq(f_str):
            if not f_str: return None
            f_str = f_str.lower().strip()
            num = "".join([c for c in f_str if c.isdigit() or c == '.'])
            val = float(num) if num else 1.0
            if "week" in f_str: return val * 7
            if "month" in f_str: return val * 30
            if "day" in f_str: return val
            if "year" in f_str: return val * 365
            if "defective" in f_str or "needed" in f_str: return 365.0
            return None

        def normalize_name(name):
            n = name.upper()
            if "REFILL" in n:
                if "PEN" in n or "INK" in n: return "BALLPEN"
                if "CORRECTION" in n: return "CORRECTION TAPE"
                if "GLUE" in n: return "GLUE"
            return name

        with SessionLocal() as session:
            target_loc_name = "MAIN OFFICE" if self.mode == "MAIN_OFFICE" else "SATELLITE OFFICE"
            
            records = session.query(
                Employee.name.label('emp'), Item.name.label('item'),
                SupplyRequest.request_date.label('date'), RequestItem.frequency.label('freq'),
                RequestItem.quantity.label('qty')
            ).select_from(Employee).join(SupplyRequest).join(RequestItem).join(Item).join(
                Location, SupplyRequest.dest_location_id == Location.id
            ).filter(Location.name == target_loc_name).order_by(Employee.name, Item.name, SupplyRequest.request_date).all()
            
            groups = {}
            for r in records:
                item = normalize_name(r.item)
                key = (r.emp, item)
                if key not in groups: groups[key] = {"dates": [], "freqs": [], "qtys": []}
                groups[key]["dates"].append(r.date)
                groups[key]["qtys"].append(r.qty)
                if r.freq: groups[key]["freqs"].append(r.freq)

            self.all_data = {}
            for (emp, item), info in groups.items():
                if emp not in self.all_data: self.all_data[emp] = []
                total = len(info["dates"])
                
                # For Main Office log, we want the raw list of requests
                raw_history = []
                for i in range(total):
                    raw_history.append({
                        "date": info["dates"][i].strftime("%Y-%m-%d"),
                        "item": item,
                        "qty": info["qtys"][i]
                    })

                days = None
                if info["freqs"]: days = parse_freq(info["freqs"][-1])
                if days is None and total > 1:
                    d = info["dates"]
                    gaps = [(d[i] - d[i-1]).days for i in range(1, len(d))]
                    days = sum(gaps)/len(gaps)
                
                status = "Insufficient Data"
                if days:
                    if days < 7: status = "🔥 High Usage"
                    elif days < 30: status = "✅ Normal"
                    else: status = "🧊 Low Usage"
                
                self.all_data[emp].append({
                    "item": item, "total": total, "days": days,
                    "weekly": f"{(7.0/days):.2f}" if days else "N/A",
                    "yearly": f"{(365.0/days):.1f}" if days else "N/A",
                    "status": status,
                    "raw": raw_history
                })

        self.emp_list.clear()
        for emp in sorted(self.all_data.keys()):
            self.emp_list.addItem(emp)

    def filter_employees(self):
        query = self.search_input.text().lower()
        for i in range(self.emp_list.count()):
            it = self.emp_list.item(i)
            it.setHidden(query not in it.text().lower())

    def on_employee_selected(self, item):
        emp = item.text()
        self.print_btn.setEnabled(True)
        stats = self.all_data.get(emp, [])

        if self.mode == "MAIN_OFFICE":
            self.log_table.setRowCount(0)
            # Combine all raw logs for this employee and sort by date
            full_history = []
            for s in stats:
                full_history.extend(s.get("raw", []))
            
            full_history.sort(key=lambda x: x["date"], reverse=True)
            
            self.log_table.setRowCount(len(full_history))
            for i, entry in enumerate(full_history):
                self.log_table.setItem(i, 0, QTableWidgetItem(entry["date"]))
                self.log_table.setItem(i, 1, QTableWidgetItem(entry["item"]))
                self.log_table.setItem(i, 2, QTableWidgetItem(str(entry["qty"])))
        else:
            while self.dash_layout.count():
                w = self.dash_layout.takeAt(0).widget()
                if w: w.deleteLater()
                
            # Lifecycle Summary Header
            with SessionLocal() as session:
                first_req = session.query(SupplyRequest).filter_by(employee_id=session.query(Employee.id).filter_by(name=emp).scalar_subquery()).order_by(SupplyRequest.request_date.asc()).first()
                tenure = "New User"
                if first_req:
                    days = (datetime.now() - first_req.request_date).days
                    tenure = f"{days} days since first issuance" if days > 0 else "First issuance today"
            
            lbl = QLabel(f"Dashboard: {emp}")
            lbl.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 10px; color: #1F4E78;")
            self.dash_layout.addWidget(lbl)
            
            tenure_lbl = QLabel(f"<i>Life Cycle: {tenure}</i>")
            tenure_lbl.setStyleSheet("color: #7f8c8d; margin-bottom: 10px;")
            self.dash_layout.addWidget(tenure_lbl)
            
            for s in stats:
                card = UsageCard(s["item"], s["days"], s["weekly"], s["yearly"], s["status"])
                self.dash_layout.addWidget(card)
            self.dash_layout.addStretch()

    def run_export(self):
        curr = self.emp_list.currentItem()
        if not curr: return
        emp = curr.text()
        stats = self.all_data.get(emp, [])
        rows = []
        for s in stats:
            rows.append((emp, s["item"], str(s["total"]), f"{s['days']:.1f}" if s["days"] else "N/A", s["weekly"], s["yearly"], s["status"]))
        try:
            filename = generate_consumption_report(rows)
            QMessageBox.information(self, "Success", f"Report saved as {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def run_print_history(self):
        """Generates a professional Excel report for this specific employee."""
        with SessionLocal() as session:
            # Query all items for this employee to get metadata (role, area, etc.)
            requests = session.query(RequestItem).join(SupplyRequest).filter(
                SupplyRequest.employee_id == self.employee_id
            ).options(
                joinedload(RequestItem.item),
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.employee),
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.department)
            ).order_by(RequestItem.id.desc()).all()

            if not requests:
                QMessageBox.warning(self, "No Data", "No history found for this employee.")
                return

            # Extract metadata from the most recent request
            latest = requests[0]
            role = latest.supply_request.employee.role or ""
            area = latest.supply_request.department.area_name or "Unknown"
            shift = latest.supply_request.department.shift or ""
            supervisor = latest.supply_request.department.supervisor or ""

            # Format data for the generator
            data_rows = []
            for r in requests:
                data_rows.append((
                    r.supply_request.request_date.strftime("%Y-%m-%d"),
                    r.item.name,
                    r.quantity,
                    "Yes" if r.is_refill_request else "No",
                    r.frequency or ""
                ))

            try:
                filename = generate_populated_report(
                    self.windowTitle().replace("Request History: ", ""),
                    role, area, shift, supervisor, data_rows
                )
                QMessageBox.information(self, "Success", f"Professional report generated: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to generate report:\n{str(e)}")

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
        
        if self.mode == "SATELLITE":
            self.area_input = QComboBox()
            self.area_input.setEditable(True)
            form_layout.addRow("Department Area:", self.area_input)
            
            self.shift_input = QLineEdit()
            form_layout.addRow("Shift:", self.shift_input)
            
            self.supervisor_input = QLineEdit()
            form_layout.addRow("Supervisor:", self.supervisor_input)
            
            self.is_refill_cb = QCheckBox("Is this a refill request?")
            form_layout.addRow("", self.is_refill_cb)
            
            self.frequency_input = QComboBox()
            self.frequency_input.setEditable(True)
            self.frequency_input.addItems(["1 WEEK", "2 WEEKS", "1 MONTH", "UNTIL DEFECTIVE", "REFILL"])
            form_layout.addRow("Frequency:", self.frequency_input)
        
        self.source_loc_input = QComboBox()
        self.dest_loc_input = QComboBox()
        form_layout.addRow("Fulfillment Source:", self.source_loc_input)
        form_layout.addRow("Requesting Office:", self.dest_loc_input)

        # Buttons
        self.submit_btn = QPushButton("Submit Request")
        self.submit_btn.clicked.connect(self.submit_request)
        
        self.clear_btn = QPushButton("Clear Form")
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
        """Creates the data table on the right side of the window."""
        self.table_panel = QVBoxLayout()
        
        # Filter Bar Layout        # Filters
        top_filter_layout = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search Employee Name or Role...")
        self.search_bar.textChanged.connect(self.filter_table)
        top_filter_layout.addWidget(self.search_bar)
        
        self.table_panel.addLayout(top_filter_layout)

        bottom_filter_layout = QHBoxLayout()
        bottom_filter_layout.addWidget(QLabel("From:"))
        self.start_date_filter = QDateEdit()
        self.start_date_filter.setCalendarPopup(True)
        self.start_date_filter.setDate(QDate.currentDate().addYears(-1))
        self.start_date_filter.dateChanged.connect(self.refresh_table)
        bottom_filter_layout.addWidget(self.start_date_filter)
        
        bottom_filter_layout.addWidget(QLabel("To:"))
        self.end_date_filter = QDateEdit()
        self.end_date_filter.setCalendarPopup(True)
        self.end_date_filter.setDate(QDate.currentDate())
        self.end_date_filter.dateChanged.connect(self.refresh_table)
        bottom_filter_layout.addWidget(self.end_date_filter)

        if self.mode == "SATELLITE":
            bottom_filter_layout.addWidget(QLabel("Area:"))
            self.area_filter = QComboBox()
            self.area_filter.addItem("ALL")
            self.area_filter.currentIndexChanged.connect(self.refresh_table)
            bottom_filter_layout.addWidget(self.area_filter)
            

        self.reset_btn = QPushButton("Reset Filter")
        self.reset_btn.clicked.connect(self.reset_filters)
        bottom_filter_layout.addWidget(self.reset_btn)
        
        self.table_panel.addLayout(bottom_filter_layout)
        
        # Clickable hint label
        hint = QLabel("<i>Double-click an employee to view their specific supply requests.</i>")
        hint.setTextFormat(Qt.TextFormat.RichText)
        self.table_panel.addWidget(hint)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels([
            "ID", "Employee Name", "Role"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # Make read-only
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self.open_employee_details)
        
        self.export_btn = QPushButton("🖨️ Print/Export Filtered Report")
        self.export_btn.clicked.connect(self.run_export)
        self.export_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        
        btn_text = "📝 Total Requested Log" if self.mode == "MAIN_OFFICE" else "📊 View Consumption/Usage Report"
        self.stats_btn = QPushButton(btn_text)
        self.stats_btn.clicked.connect(self.open_consumption_report)
        self.stats_btn.setStyleSheet("background-color: #E1F5FE; font-weight: bold;")
        
        self.table_panel.addWidget(self.table)
        
        # Button layout at bottom right
        btn_box = QHBoxLayout()
        self.delete_emp_btn = QPushButton("Delete Selected Employee")
        self.delete_emp_btn.clicked.connect(self.delete_selected_employee)
        self.delete_emp_btn.setStyleSheet("color: #c0392b; font-weight: bold;")
        
        btn_box.addWidget(self.delete_emp_btn)
        btn_box.addWidget(self.export_btn)
        btn_box.addWidget(self.stats_btn)
        self.table_panel.addLayout(btn_box)
        
        self.main_layout.addLayout(self.table_panel, 3) # 3 parts width

    def load_dropdowns(self):
        """Pre-fills dropdowns with data already in the database."""
        with SessionLocal() as session:
            locations = session.query(Location).all()
            for loc in locations:
                self.source_loc_input.addItem(loc.name, loc.id)
                self.dest_loc_input.addItem(loc.name, loc.id)
                
            # Determine target location based on mode
            target_loc_name = "MAIN OFFICE" if self.mode == "MAIN_OFFICE" else "SATELLITE OFFICE"

            # Default logic for new requests
            w_idx = self.source_loc_input.findText("WAREHOUSE")
            if w_idx >= 0: self.source_loc_input.setCurrentIndex(w_idx)
            
            m_idx = self.dest_loc_input.findText(target_loc_name)
            if m_idx >= 0: 
                self.dest_loc_input.setCurrentIndex(m_idx)
                # Lock the destination location to prevent cross-contamination
                self.dest_loc_input.setEnabled(False)
            
            # Load item names
            items = session.query(Item).all()
            self.item_name_input.addItems([i.name for i in items])
            
            if self.mode == "SATELLITE":
                # Load existing Areas for autocomplete
                distinct_areas = session.query(Department.area_name).distinct().all()
                self.area_input.addItems([a[0] for a in distinct_areas if a[0]])
                
                # Load into filter dropdown too
                self.area_filter.addItems([a[0] for a in distinct_areas if a[0]])


    def submit_request(self):
        """Handles saving form data into SQLite via SQLAlchemy."""
        emp_name = self.emp_name_input.currentText().strip()
        qty_str = self.quantity_input.text().strip()
        item_name = self.item_name_input.currentText().strip()
        
        # Collect secondary fields (Conditional)
        role = self.emp_role_input.text().strip()
        area = "N/A"
        shift = "N/A"
        supervisor = "N/A"
        is_refill = False
        freq = "N/A"
        
        if self.mode == "SATELLITE":
            area = self.area_input.currentText().strip()
            shift = self.shift_input.text().strip()
            supervisor = self.supervisor_input.text().strip()
            is_refill = self.is_refill_cb.isChecked()
            freq = self.frequency_input.currentText().strip()

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
                emp = session.query(Employee).filter_by(name=emp_name).first()
                if not emp:
                    emp = Employee(name=emp_name, role=self.emp_role_input.text().strip())
                    session.add(emp)
                    session.flush()
                
                # 2. Get or Create Department
                dept = session.query(Department).filter_by(
                    area_name=area, 
                    shift=shift,
                    supervisor=supervisor
                ).first()
                if not dept:
                    dept = Department(
                        area_name=area, 
                        shift=shift, 
                        supervisor=supervisor
                    )
                    session.add(dept)
                    session.flush()

                # 3. Get or Create Item
                item = session.query(Item).filter_by(name=item_name).first()
                if not item:
                    item = Item(name=item_name)
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
                    is_refill_request=is_refill,
                    frequency=freq
                )
                session.add(req_item)

                # 6. Deduct Stock from Source
                source_id = self.source_loc_input.currentData()
                stock = session.query(Stock).filter_by(item_id=item.id, location_id=source_id).first()
                if stock:
                    stock.quantity -= qty_float
                else:
                    # If no stock entry exists, assume 0 and go negative (allowance for missing initial data)
                    new_stock = Stock(item_id=item.id, location_id=source_id, quantity=-qty_float)
                    session.add(new_stock)
                
                session.commit()
                QMessageBox.information(self, "Success", "Supply request successfully logged!")
                
                self.clear_form(full=False)
                self.refresh_table()
                
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Database Error", f"Failed to save to database:\n{str(e)}")

    def refresh_table(self):
        """Loads a list of distinct employees and their request count matching the date, area, and shift filters."""
        self.table.setRowCount(0)
        
        # Get Filters (Conditional)
        search_text = self.search_bar.text().lower().strip()
        start_qdate = self.start_date_filter.date()
        end_qdate = self.end_date_filter.date()
        
        start_dt = datetime(start_qdate.year(), start_qdate.month(), start_qdate.day(), 0, 0, 0)
        end_dt = datetime(end_qdate.year(), end_qdate.month(), end_qdate.day(), 23, 59, 59)
        
        area_filter = None
        shift_filter = None
        
        if self.mode == "SATELLITE":
            area_filter = self.area_filter.currentText()

        with SessionLocal() as session:
            # We need to find the latest info for every employee
            # This is complex in one query, so we'll fetch base stats and then enrich
            query = session.query(
                Employee.id,
                Employee.name,
                Employee.role,
                func.max(SupplyRequest.request_date).label('last_date')
            ).outerjoin(SupplyRequest, Employee.id == SupplyRequest.employee_id) \
             .outerjoin(Department, SupplyRequest.department_id == Department.id)
            
            if search_text:
                query = query.filter((Employee.name.ilike(f"%{search_text}%")) | (Employee.role.ilike(f"%{search_text}%")))

            if area_filter and area_filter != "ALL":
                query = query.filter(Department.area_name == area_filter)

            # Filtering by date range (only if they have requests)
            # Actually, standard view should show all employees, but count requests in range
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
                # If they have requests, only show them if their latest request matches THIS tab's office.
                if latest_req and latest_req.dest_location:
                    if latest_req.dest_location.name != target_loc_name:
                        continue
                elif self.mode == "MAIN_OFFICE":
                    if not latest_req:
                        continue

                area_name = latest_req.department.area_name if latest_req and latest_req.department else "N/A"
                shift_val = latest_req.department.shift if latest_req and latest_req.department else "N/A"
                
                # 2. Determine "Pending" status based on explicit database column
                self.table.insertRow(row_idx)
                self.table.setItem(row_idx, 0, QTableWidgetItem(str(emp.id)))
                self.table.setItem(row_idx, 1, QTableWidgetItem(emp.name))
                self.table.setItem(row_idx, 2, QTableWidgetItem(emp.role or "N/A"))
                
                row_idx += 1
        self.filter_table()
                
    def run_search(self):
        """Triggers both database refresh (dates) and local filtering (text)."""
        self.refresh_table()

    def reset_filters(self):
        """Reset search and date filters to defaults."""
        self.search_bar.clear()
        self.start_date_filter.setDate(QDate.currentDate().addYears(-1))
        self.end_date_filter.setDate(QDate.currentDate())
        self.refresh_table()

    def open_employee_details(self, row, column):
        """Opens a dialog showing the specific items this employee requested."""
        emp_id = int(self.table.item(row, 0).text())
        emp_name = self.table.item(row, 1).text()
        
        dialog = EmployeeDetailsDialog(employee_id=emp_id, employee_name=emp_name, mode=self.mode, parent=self)
        dialog.exec()

    def open_consumption_report(self):
        """Opens the overall consumption analysis report."""
        dialog = ConsumptionReportDialog(mode=self.mode, parent=self)
        dialog.exec()

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
        
        if self.mode == "SATELLITE":
            self.shift_input.clear()

    def filter_table(self):
        """Hides or shows rows based on search text."""
        search_text = self.search_bar.text().lower()
        for row in range(self.table.rowCount()):
            match = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    def run_export(self):
        try:
            # Get current filter values
            start_qdate = self.start_date_filter.date()
            end_qdate = self.end_date_filter.date()
            start_dt = datetime(start_qdate.year(), start_qdate.month(), start_qdate.day())
            end_dt = datetime(end_qdate.year(), end_qdate.month(), end_qdate.day(), 23, 59, 59)
            
            area = None
            
            if self.mode == "SATELLITE":
                area = self.area_filter.currentText()
                if area == "ALL": area = None

            exported_path = export_to_excel(
                start_date=start_dt,
                end_date=end_dt,
                area=area,
                only_pending=False
            )
            
            if exported_path:
                QMessageBox.information(self, "Export Successful", f"Filtered report successfully exported to:\n{exported_path}")
            else:
                QMessageBox.warning(self, "No Data", "No matching records found for the current filters.")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export data:\n{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Optional: Set a clean, modern stylesheet if desired
    app.setStyle("Fusion")
    
    window = RequestTrackingApp()
    window.show()
    sys.exit(app.exec())
