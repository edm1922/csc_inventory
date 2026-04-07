import os
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, 
                             QHeaderView, QGroupBox, QFormLayout, QDialog, QComboBox, 
                             QDateEdit, QAbstractItemView, QMenu)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QFont, QColor

from core.database import SessionLocal, Item, Location, Stock, QuickPullLog, QuickPullItem, InventoryActionLog, Employee
from sqlalchemy.orm import joinedload
import qrcode
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

class QuickPullEntryDialog(QDialog):
    """Dialog to record a new item release (Quick Pull)."""
    def __init__(self, log_id=None, parent=None):
        super().__init__(parent)
        self.log_id = log_id
        self.setWindowTitle("Record New Item Release (Quick Pull)" if not log_id else "Edit Item Release Record")
        self.setMinimumSize(700, 500)
        
        self.main_layout = QVBoxLayout(self)
        
        # 1. Transaction Info
        info_group = QGroupBox("Transaction Information")
        info_layout = QFormLayout(info_group)
        
        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        
        self.requester_input = QLineEdit()
        self.requester_input.setPlaceholderText("Name of person receiving the items")
        
        self.purpose_input = QLineEdit()
        self.purpose_input.setPlaceholderText("Remarks or reason for release")
        
        self.destination_input = QLineEdit()
        self.destination_input.setPlaceholderText("Company or Agency destination")
        
        self.location_cb = QComboBox()
        self.load_locations()
        self.location_cb.currentIndexChanged.connect(self.refresh_available_stock)
        
        info_layout.addRow("Date:", self.date_input)
        info_layout.addRow("Requested By:", self.requester_input)
        info_layout.addRow("Remarks:", self.purpose_input)
        info_layout.addRow("Where To:", self.destination_input)
        info_layout.addRow("Source Location:", self.location_cb)
        
        self.main_layout.addWidget(info_group)
        
        # 2. Item Selection
        item_group = QGroupBox("Items to Release")
        item_layout = QVBoxLayout(item_group)
        
        # Add Item Selection Row
        sel_layout = QHBoxLayout()
        self.item_selector = QComboBox()
        self.item_selector.setEditable(True)
        self.item_selector.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.load_items()
        sel_layout.addWidget(QLabel("Select Item:"))
        sel_layout.addWidget(self.item_selector, 2)
        
        self.add_item_btn = QPushButton("+ Add to List")
        self.add_item_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.add_item_btn.clicked.connect(self.add_item_to_list)
        sel_layout.addWidget(self.add_item_btn)
        
        self.remove_item_btn = QPushButton("🗑 Remove Selected")
        self.remove_item_btn.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.remove_item_btn.clicked.connect(self.remove_selected_item)
        sel_layout.addWidget(self.remove_item_btn)
        
        item_layout.addLayout(sel_layout)
        
        # Selected Items Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Item Name", "Description", "Available", "Pull Quantity", "ID"])
        self.table.setColumnHidden(4, True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setStyleSheet("QTableWidget { background: white; color: black; }")
        item_layout.addWidget(self.table)
        
        self.main_layout.addWidget(item_group)
        
        # 3. Actions
        btn_layout = QHBoxLayout()
        self.submit_btn.setDefault(True)
        
        cancel_btn = QPushButton("&Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.submit_btn)
        self.main_layout.addLayout(btn_layout)
        
        # UX: Set initial focus to Requester
        self.requester_input.setFocus()
        
        if self.log_id:
            self.load_log_data()

    def load_locations(self):
        with SessionLocal() as session:
            locations = session.query(Location).all()
            for loc in locations:
                self.location_cb.addItem(loc.name, loc.id)

    def load_items(self):
        with SessionLocal() as session:
            items = session.query(Item).order_by(Item.name).all()
            for item in items:
                label = f"{item.name}"
                if item.description:
                    label += f" - {item.description}"
                self.item_selector.addItem(label, item.id)

    def refresh_available_stock(self):
        """Updates the available quantity column for all items currently in the list."""
        loc_id = self.location_cb.currentData()
        with SessionLocal() as session:
            for row in range(self.table.rowCount()):
                item_id = int(self.table.item(row, 4).text())
                stock = session.query(Stock).filter_by(item_id=item_id, location_id=loc_id).first()
                qty = stock.quantity if stock else 0.0
                self.table.setItem(row, 2, QTableWidgetItem(f"{qty:.2f}"))

    def add_item_to_list(self):
        item_id = self.item_selector.currentData()
        item_name = self.item_selector.currentText()
        if not item_id: return
        
        # Check if already added
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).text() == item_name:
                return

        loc_id = self.location_cb.currentData()
        with SessionLocal() as session:
            item = session.query(Item).get(item_id)
            stock = session.query(Stock).filter_by(item_id=item_id, location_id=loc_id).first()
            available = stock.quantity if stock else 0.0
            description = item.description if item else ""
            
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(item_name.split(" - ")[0]))
        self.table.setItem(row, 1, QTableWidgetItem(description))
        
        avail_item = QTableWidgetItem(f"{available:.2f}")
        avail_item.setFlags(avail_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 2, avail_item)
        
        pull_input = QTableWidgetItem("1.00")
        self.table.setItem(row, 3, pull_input)
        
        self.table.setItem(row, 4, QTableWidgetItem(str(item_id)))

    def remove_selected_item(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        
        # Sort in reverse to delete from bottom up
        for index in sorted(selected, reverse=True):
            self.table.removeRow(index.row())

    def load_log_data(self):
        """Loads existing log and items into the form for editing."""
        with SessionLocal() as session:
            log = session.query(QuickPullLog).options(
                joinedload(QuickPullLog.pulled_items).joinedload(QuickPullItem.item)
            ).get(self.log_id)
            
            if log:
                self.date_input.setDate(QDate(log.date.year, log.date.month, log.date.day))
                self.requester_input.setText(log.requested_by)
                self.purpose_input.setText(log.purpose or "")
                self.destination_input.setText(log.destination or "")
                
                # Set location (Find index by data)
                idx = self.location_cb.findData(log.source_location_id)
                self.location_cb.setCurrentIndex(idx)
                
                # Load items
                for pi in log.pulled_items:
                    if not pi.item:
                        continue # Skip deleted items
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    self.table.setItem(row, 0, QTableWidgetItem(pi.item.name))
                    self.table.setItem(row, 1, QTableWidgetItem(pi.item.description or ""))
                    
                    # Available stock (Current + what was pulled)
                    stock = session.query(Stock).filter_by(item_id=pi.item_id, location_id=log.source_location_id).first()
                    avail = stock.quantity if stock else 0.0
                    
                    avail_item = QTableWidgetItem(f"{avail:.2f}")
                    avail_item.setFlags(avail_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row, 2, avail_item)
                    
                    self.table.setItem(row, 3, QTableWidgetItem(f"{pi.quantity:.2f}"))
                    self.table.setItem(row, 4, QTableWidgetItem(str(pi.item_id)))

    def validate_and_submit(self):
        # 1. Validation
        if not self.requester_input.text().strip():
            QMessageBox.warning(self, "Missing Info", "Please enter who is requesting these items.")
            return
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Items", "Please add at least one item to pull.")
            return
            
        loc_id = self.location_cb.currentData()
        loc_name = self.location_cb.currentText()
        items_to_pull = []
        
        try:
            for row in range(self.table.rowCount()):
                item_name = self.table.item(row, 0).text()
                available = float(self.table.item(row, 2).text())
                pull_qty = float(self.table.item(row, 3).text())
                item_id = int(self.table.item(row, 4).text())
                
                if pull_qty <= 0:
                    raise ValueError(f"Quantity for {item_name} must be greater than zero.")
                if pull_qty > available:
                    raise ValueError(f"Insufficient stock for {item_name} at {loc_name}. Available: {available}")
                
                items_to_pull.append({
                    "id": item_id,
                    "name": item_name,
                    "qty": pull_qty
                })
        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
            return

        # 2. Transaction
        with SessionLocal() as session:
            try:
                # 2.1 Reversal Logic (If Editing)
                if self.log_id:
                    old_log = session.query(QuickPullLog).options(joinedload(QuickPullLog.pulled_items)).get(self.log_id)
                    # Add back old quantities to stock
                    for old_pi in old_log.pulled_items:
                        old_stock = session.query(Stock).filter_by(
                            item_id=old_pi.item_id, 
                            location_id=old_log.source_location_id
                        ).first()
                        if old_stock:
                            old_stock.quantity += old_pi.quantity
                    
                    # Delete old item entries
                    for old_pi in old_log.pulled_items:
                        session.delete(old_pi)
                    
                    log = old_log
                else:
                    log = QuickPullLog()
                    session.add(log)

                # 2.2 Update Metadata
                dt = datetime.combine(self.date_input.date().toPyDate(), datetime.now().time())
                log.date = dt
                log.requested_by = self.requester_input.text().strip().upper()
                log.purpose = self.purpose_input.text().strip().upper()
                log.destination = self.destination_input.text().strip().upper()
                log.source_location_id = loc_id
                
                session.flush() # Get/Update log.id
                
                # 2.3 Record New Items and Deduct Inventory
                for clip in items_to_pull:
                    p_item = QuickPullItem(
                        log_id=log.id,
                        item_id=clip["id"],
                        quantity=clip["qty"]
                    )
                    session.add(p_item)
                    
                    # Deduct from Stock (at the potentially NEW location)
                    stock = session.query(Stock).filter_by(item_id=clip["id"], location_id=loc_id).first()
                    if not stock: # Handle edge case where stock entry might be missing for a location
                         stock = Stock(item_id=clip["id"], location_id=loc_id, quantity=0.0)
                         session.add(stock)
                    stock.quantity -= clip["qty"]
                    
                    # 2.4 Log to Activity Log
                    log_entry = InventoryActionLog(
                        timestamp=datetime.now(),
                        item_name=clip["name"],
                        action_type="REMOVED",
                        details=f"Quick Pull: {clip['qty']:.2f} units pulled by {log.requested_by}. Remaining Stock: {stock.quantity:.2f}",
                        user=log.requested_by
                    )
                    session.add(log_entry)
                
                session.commit()
                QMessageBox.information(self, "Success", "Record saved and inventory adjusted.")
                self.accept()
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to save record: {e}")

class TaggingDialog(QDialog):
    """Dialog for manual tagging and generating QR codes for item releases."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Release Tagging / QR Generator")
        self.setMinimumWidth(500)
        self.db_log_id = None # Track if we've already logged this session
        
        self.main_layout = QVBoxLayout(self)
        
        form_group = QGroupBox("Release Information")
        form = QFormLayout(form_group)
        
        self.date_issued = QDateEdit(QDate.currentDate())
        self.date_issued.setCalendarPopup(True)
        
        self.date_hired = QDateEdit(QDate.currentDate())
        self.date_hired.setCalendarPopup(True)
        
        self.emp_name = QComboBox()
        self.emp_name.setEditable(True)
        self.load_employees()
        
        self.emp_role = QLineEdit()
        self.dept_area = QLineEdit()
        self.remarks = QLineEdit()
        
        self.source_cb = QComboBox()
        self.load_locations()
        
        self.item_cb = QComboBox()
        self.item_cb.setEditable(True)
        self.load_items()
        
        # Reset log tracking if data changes
        self.emp_name.currentTextChanged.connect(self.reset_log_tracking)
        self.item_cb.currentTextChanged.connect(self.reset_log_tracking)
        self.source_cb.currentTextChanged.connect(self.reset_log_tracking)
        
        form.addRow("Issued Date:", self.date_issued)
        form.addRow("Date Hired:", self.date_hired)
        form.addRow("Employee Name:", self.emp_name)
        form.addRow("Employee Role:", self.emp_role)
        form.addRow("Department Area:", self.dept_area)
        form.addRow("Remarks:", self.remarks)
        form.addRow("Source Fulfilment:", self.source_cb)
        form.addRow("Item Requested:", self.item_cb)
        
        self.main_layout.addWidget(form_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.print_btn = QPushButton("🖨️ &Print Form (PDF)")
        self.print_btn.setStyleSheet("background-color: #2980b9; color: white; padding: 10px; font-weight: bold;")
        self.print_btn.clicked.connect(self.generate_form_pdf)
        
        self.qr_btn = QPushButton("📱 &Generate QR Code")
        self.qr_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 10px; font-weight: bold;")
        self.qr_btn.clicked.connect(self.generate_qr_code)
        
        cancel_btn = QPushButton("&Close")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.print_btn)
        btn_layout.addWidget(self.qr_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        self.main_layout.addLayout(btn_layout)
        
        # UX: Set focus to Emp Name
        self.emp_name.setFocus()

    def load_employees(self):
        with SessionLocal() as session:
            emps = session.query(Employee).order_by(Employee.name).all()
            for e in emps:
                self.emp_name.addItem(e.name, e.role)
        self.emp_name.currentIndexChanged.connect(self.auto_fill_role)

    def auto_fill_role(self, idx):
        role = self.emp_name.itemData(idx)
        if role:
            self.emp_role.setText(role)

    def load_locations(self):
        with SessionLocal() as session:
            locs = session.query(Location).all()
            for l in locs:
                self.source_cb.addItem(l.name)

    def load_items(self):
        with SessionLocal() as session:
            items = session.query(Item).order_by(Item.name).all()
            for it in items:
                label = f"{it.name}"
                if it.description:
                    label += f" - {it.description}"
                self.item_cb.addItem(label, it.id)

    def get_form_data(self):
        return {
            "issued_date": self.date_issued.date().toString("yyyy-MM-dd"),
            "date_hired": self.date_hired.date().toString("yyyy-MM-dd"),
            "emp_name": self.emp_name.currentText().upper(),
            "emp_role": self.emp_role.text().upper(),
            "area": self.dept_area.text().upper(),
            "remarks": self.remarks.text().upper(),
            "source": self.source_cb.currentText().upper(),
            "item": self.item_cb.currentText().upper(),
            "item_id": self.item_cb.currentData()
        }

    def reset_log_tracking(self):
        self.db_log_id = None

    def log_to_database(self):
        """Deducts stock and creates a Quick Pull log entry."""
        if self.db_log_id:
            return True # Already logged this session
            
        data = self.get_form_data()
        
        # Basic validation
        if not data["emp_name"] or not data["item"] or not data["source"]:
            QMessageBox.warning(self, "Incomplete Data", "Please ensure Employee, Item, and Source are filled.")
            return False

        reply = QMessageBox.question(self, "Confirm Log", 
                                   f"This will deduct 1.0 unit of '{data['item']}' from '{data['source']}' and log the pull.\n\nProceed?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            return False

        with SessionLocal() as session:
            try:
                # 1. Find Item and Location
                if data["item_id"]:
                    item = session.query(Item).get(data["item_id"])
                else:
                    # Fallback for manual typing
                    name_only = data["item"].split(" - ")[0]
                    item = session.query(Item).filter(Item.name == name_only).first()
                
                loc = session.query(Location).filter(Location.name == data["source"]).first()
                
                if not item:
                    QMessageBox.warning(self, "Error", f"Item '{data['item']}' not found in database.")
                    return False
                if not loc:
                    QMessageBox.warning(self, "Error", f"Location '{data['source']}' not found in database.")
                    return False
                
                # 2. Check and Deduct Stock
                stock = session.query(Stock).filter_by(item_id=item.id, location_id=loc.id).first()
                if not stock or stock.quantity < 1.0:
                    available = stock.quantity if stock else 0.0
                    QMessageBox.warning(self, "Insufficient Stock", f"Only {available:.2f} available at {data['source']}.")
                    return False
                
                stock.quantity -= 1.0
                
                # 3. Create Quick Pull Log
                log = QuickPullLog(
                    date=datetime.now(),
                    requested_by=data["emp_name"],
                    purpose=data["remarks"],
                    destination=data["area"],
                    source_location_id=loc.id
                )
                session.add(log)
                session.flush() # Get log.id
                
                # 4. Create Quick Pull Item
                p_item = QuickPullItem(
                    log_id=log.id,
                    item_id=item.id,
                    quantity=1.0
                )
                session.add(p_item)
                
                # 5. Inventory Action Log
                action_log = InventoryActionLog(
                    timestamp=datetime.now(),
                    item_name=item.name,
                    action_type="REMOVED",
                    details=f"Tagged Release: 1.0 unit pulled by {data['emp_name']}. Source: {data['source']}",
                    user=data["emp_name"]
                )
                session.add(action_log)
                
                session.commit()
                self.db_log_id = log.id
                return True
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to log transaction: {e}")
                return False

    def generate_form_pdf(self):
        if not self.log_to_database():
            return
            
        data = self.get_form_data()
        filename = f"RELEASE_TAG_{data['emp_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        
        try:
            c = canvas.Canvas(filename, pagesize=letter)
            width, height = letter
            
            # Header
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(width/2, height - 50, "ITEM RELEASE / TAGGING FORM")
            
            c.setFont("Helvetica", 12)
            c.line(50, height - 60, width - 50, height - 60)
            
            y = height - 100
            line_height = 25
            
            headers = [
                ("Issued Date:", data['issued_date']),
                ("Date Hired:", data['date_hired']),
                ("Employee Name:", data['emp_name']),
                ("Employee Role:", data['emp_role']),
                ("Department Area:", data['area']),
                ("Remarks:", data['remarks']),
                ("Source Fulfillment:", data['source']),
                ("Item Requested:", data['item'])
            ]
            
            for label, val in headers:
                c.setFont("Helvetica-Bold", 11)
                c.drawString(70, y, label)
                c.setFont("Helvetica", 11)
                c.drawString(200, y, str(val))
                y -= line_height

            # Signatures
            y -= 40
            c.line(70, y, 220, y)
            c.line(width - 220, y, width - 70, y)
            
            c.setFont("Helvetica", 10)
            c.drawCentredString(145, y - 15, "Prepared By")
            c.drawCentredString(width - 145, y - 15, "Approved By")
            
            c.save()
            os.startfile(filename)
            QMessageBox.information(self, "Success", f"PDF Form generated: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {e}")

    def generate_qr_code(self):
        if not self.log_to_database():
            return
            
        data = self.get_form_data()
        
        # We use a consolidated vCard 3.0 format.
        # To ensure all scanners show the 'Most Important' data, 
        # we put everything into the NOTE field with clear labels.
        vcard_payload = (
            f"BEGIN:VCARD\n"
            f"VERSION:3.0\n"
            f"FN:TAG: {data['item']}\n"
            f"ORG:{data['area']}\n"
            f"NOTE:ITEM    : {data['item']}\\n"
            f"EMPLOYEE: {data['emp_name']}\\n"
            f"ROLE    : {data['emp_role']}\\n"
            f"AREA    : {data['area']}\\n"
            f"SOURCE  : {data['source']}\\n"
            f"DATE    : {data['issued_date']}\\n"
            f"--------------------------\\n"
            f"REMARKS : {data['remarks']}\\n"
            f"ID      : {self.db_log_id or 'N/A'}\\n"
            f"SYSTEM  : Unified Inventory\n"
            f"END:VCARD"
        )
        
        qr_payload = vcard_payload
        
        filename = f"QR_{data['emp_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        
        try:
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10, 
                border=4
            )
            qr.add_data(qr_payload)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="#1a2a6c", back_color="white")
            img.save(filename)
            
            os.startfile(filename)
            QMessageBox.information(self, "Success", f"QR Code generated as a Comprehensive Record Card: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate QR: {e}")

class QuickPullManager(QWidget):
    """Main view for Quick Pull logbook."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Quick Pull Logbook")
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50; margin-bottom: 2px;")
        self.main_layout.addWidget(header)
        
        self.status_lbl = QLabel("Showing all logs")
        self.status_lbl.setStyleSheet("color: #7f8c8d; font-size: 11px; margin-bottom: 10px;")
        self.main_layout.addWidget(self.status_lbl)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("➕ Record New Release (Pull)")
        self.add_btn.setStyleSheet("padding: 10px; background-color: #27ae60; color: white; font-weight: bold; border-radius: 5px;")
        self.add_btn.clicked.connect(self.open_add_dialog)
        toolbar.addWidget(self.add_btn)

        self.tag_btn = QPushButton("🏷️ Tagging / QR Gen")
        self.tag_btn.setStyleSheet("padding: 10px; background-color: #8e44ad; color: white; font-weight: bold; border-radius: 5px;")
        self.tag_btn.clicked.connect(self.open_tagging_dialog)
        toolbar.addWidget(self.tag_btn)
        
        self.delete_btn = QPushButton("🗑 Delete Selected")
        self.delete_btn.setStyleSheet("padding: 10px; background-color: #c0392b; color: white; font-weight: bold; border-radius: 5px;")
        self.delete_btn.clicked.connect(self.delete_selected_logs)
        toolbar.addWidget(self.delete_btn)
        
        toolbar.addStretch()
        
        # Search Debounce Timer
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300) # Wait 300ms until user stops typing
        self.search_timer.timeout.connect(self.load_logs)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter logs by requester, remarks, or item...")
        self.search_input.setFixedWidth(300)
        self.search_input.textChanged.connect(self.search_timer.start)
        toolbar.addWidget(self.search_input)
        
        self.main_layout.addLayout(toolbar)
        
        # Log Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Date", "Requested By", "Items Pulled", "Location", "Remarks", "Destination", "ID"])
        self.table.setColumnHidden(6, True)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self.edit_log)
        self.table.setStyleSheet("QTableWidget { background: white; color: black; }")
        self.main_layout.addWidget(self.table)
        
        self.load_logs()

    def open_add_dialog(self):
        d = QuickPullEntryDialog(None, self)
        if d.exec():
            self.load_logs()

    def open_tagging_dialog(self):
        d = TaggingDialog(self)
        d.exec()
        self.load_logs() # Refresh main table in case items were logged

    def edit_log(self, row, col):
        log_id = int(self.table.item(row, 6).text())
        d = QuickPullEntryDialog(log_id, self)
        if d.exec():
            self.load_logs()

    def delete_selected_logs(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
             QMessageBox.warning(self, "No Selection", "Please select logs to delete.")
             return
        
        reply = QMessageBox.question(self, "Confirm Delete", 
                                   f"Are you sure you want to delete {len(selected_rows)} record(s)?\n\nStock levels will be reversed (restored).",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            with SessionLocal() as session:
                try:
                    for row_proxy in selected_rows:
                        log_id = int(self.table.item(row_proxy.row(), 6).text())
                        log = session.query(QuickPullLog).options(joinedload(QuickPullLog.pulled_items)).get(log_id)
                        if log:
                            # Reverse Stock
                            for pi in log.pulled_items:
                                stock = session.query(Stock).filter_by(item_id=pi.item_id, location_id=log.source_location_id).first()
                                if stock:
                                    stock.quantity += pi.quantity
                            session.delete(log)
                    session.commit()
                    self.load_logs()
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Error", f"Deletion failed: {e}")

    def load_logs(self):
        search = self.search_input.text().strip().upper()
        with SessionLocal() as session:
            query = session.query(QuickPullLog).options(
                joinedload(QuickPullLog.pulled_items).joinedload(QuickPullItem.item),
                joinedload(QuickPullLog.source_location)
            ).order_by(QuickPullLog.date.desc())
            
            if search:
                # Comprehensive filtering by requester, purpose, destination, location, or associated items
                query = query.join(QuickPullLog.source_location).filter(
                    (QuickPullLog.requested_by.contains(search)) |
                    (QuickPullLog.purpose.contains(search)) |
                    (QuickPullLog.destination.contains(search)) |
                    (Location.name.contains(search)) |
                    (QuickPullLog.pulled_items.any(
                        QuickPullItem.item.has(
                            (Item.name.contains(search)) |
                            (Item.description.contains(search))
                        )
                    ))
                ).distinct()
            
            logs = query.all()
            
            self.table.setRowCount(len(logs))
            
            # UX: Update status label
            if len(logs) == 0:
                self.status_lbl.setText("No release records found matching your search.")
                self.status_lbl.setStyleSheet("color: #c0392b; font-weight: bold; font-size: 11px; margin-bottom: 10px;")
            else:
                self.status_lbl.setText(f"Showing {len(logs)} release records")
                self.status_lbl.setStyleSheet("color: #7f8c8d; font-size: 11px; margin-bottom: 10px;")
            for i, log in enumerate(logs):
                self.table.setItem(i, 0, QTableWidgetItem(log.date.strftime("%Y-%m-%d %H:%M")))
                self.table.setItem(i, 1, QTableWidgetItem(log.requested_by))
                
                # Format items summary: "Item A - Description (5), Item B (2)"
                items_list = []
                for pi in log.pulled_items:
                    if not pi.item:
                        items_list.append(f"Deleted Item ({pi.quantity:.2f})")
                        continue
                    summary = f"{pi.item.name}"
                    if pi.item.description:
                         summary += f" - {pi.item.description}"
                    summary += f" ({pi.quantity:.2f})"
                    items_list.append(summary)
                
                items_summary = ", ".join(items_list)
                self.table.setItem(i, 2, QTableWidgetItem(items_summary))
                
                self.table.setItem(i, 3, QTableWidgetItem(log.source_location.name))
                self.table.setItem(i, 4, QTableWidgetItem(log.purpose))
                self.table.setItem(i, 5, QTableWidgetItem(log.destination))
                self.table.setItem(i, 6, QTableWidgetItem(str(log.id)))
