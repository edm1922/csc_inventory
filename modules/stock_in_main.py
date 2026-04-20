import os
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, 
                             QHeaderView, QGroupBox, QFormLayout, QDialog, QComboBox, 
                             QDateEdit, QAbstractItemView, QMenu, QCompleter)
from PyQt6.QtCore import Qt, QDate, QTimer, QStringListModel

from core.database import SessionLocal, Item, Location, Stock, StockInLog, StockInItem, InventoryActionLog, Employee
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def generate_stock_in_pdf(data, items_data, filename=None):
    if not filename:
        filename = f"STOCK_IN_{data['receiver'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    
    try:
        c = canvas.Canvas(filename, pagesize=letter)
        width, height = letter
        
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width/2, height - 50, "STOCK IN TRANSMITTAL")
        
        c.setFont("Helvetica", 12)
        c.line(50, height - 60, width - 50, height - 60)
        
        y = height - 90
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "RECEIVED BY:")
        c.drawString(330, y, "DATE:")
        
        c.setFont("Helvetica", 11)
        c.drawString(140, y, data["receiver"])
        c.drawString(380, y, data["date"])
        
        y -= 20
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "DESTINATION:")
        c.drawString(330, y, "SOURCE/REMARKS:")
        
        c.setFont("Helvetica", 11)
        c.drawString(140, y, data["location"])
        c.drawString(450, y, data["remarks"])
        
        y -= 30
        c.line(50, y, width - 50, y)
        
        # Table Header
        y -= 25
        c.setFont("Helvetica-Bold", 11)
        c.drawString(60, y, "Item Name")
        c.drawString(250, y, "Description")
        c.drawString(480, y, "Quantity Added")
        c.line(50, y - 5, width - 50, y - 5)
        
        y -= 25
        c.setFont("Helvetica", 11)
        for item in items_data:
            c.drawString(60, y, item["name"][:30])
            c.drawString(250, y, str(item.get("desc", ""))[:35])
            c.drawString(480, y, str(item["qty"]))
            y -= 20
            if y < 150: # Leave space for signatures
                c.showPage()
                c.setFont("Helvetica", 11)
                y = height - 50
                
        # Signatures section
        if y < 120:
            c.showPage()
            y = height - 50
            
        y -= 50
        c.setFont("Helvetica", 10)
        c.drawString(50, y, "Prepared By:")
        c.drawString(300, y, "Received By:")
        
        y -= 30
        c.line(50, y, 220, y)
        c.line(300, y, 470, y)
        
        y -= 15
        c.setFont("Helvetica", 8)
        c.drawString(50, y, "Signature over Printed Name")
        c.drawString(300, y, "Signature over Printed Name")
                
        c.save()
        os.startfile(filename)
        return True, filename
    except Exception as e:
        return False, str(e)

class StockInEntryDialog(QDialog):
    """Dialog to record new items arriving (Stock In)."""
    def __init__(self, log_id=None, parent=None, preselected_items=None):
        super().__init__(parent)
        self.log_id = log_id
        self.setWindowTitle("Record Stock In" if not log_id else "Edit Stock In Record")
        self.setMinimumSize(700, 500)
        
        # Track whether the form has been logged to DB to avoid double-logging before printing PDF
        self.db_log_id = log_id
        
        self.main_layout = QVBoxLayout(self)
        
        # 1. Transaction Info
        info_group = QGroupBox("Arrival Information")
        info_layout = QFormLayout(info_group)
        
        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        
        self.receiver_input = QLineEdit()
        self.receiver_input.setPlaceholderText("Name of person receiving the items")
        
        self.remarks_input = QLineEdit()
        self.remarks_input.setPlaceholderText("Supplier / Source / Remarks")
        
        self.location_cb = QComboBox()
        self.load_locations()
        self.location_cb.currentIndexChanged.connect(self.refresh_current_stock)
        
        info_layout.addRow("Date:", self.date_input)
        info_layout.addRow("Received By:", self.receiver_input)
        info_layout.addRow("Remarks/Source:", self.remarks_input)
        info_layout.addRow("Destination Location:", self.location_cb)
        
        self.main_layout.addWidget(info_group)
        
        # Reset log tracking if metadata changes
        self.receiver_input.textChanged.connect(self.reset_log_tracking)
        self.remarks_input.textChanged.connect(self.reset_log_tracking)
        self.location_cb.currentIndexChanged.connect(self.reset_log_tracking)
        
        # 2. Item Selection
        item_group = QGroupBox("Items to Stock In")
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
        self.add_item_btn.setProperty("class", "primary")
        self.add_item_btn.clicked.connect(self.add_item_to_list)
        sel_layout.addWidget(self.add_item_btn)
        
        self.remove_item_btn = QPushButton("🗑 Remove Selected")
        self.remove_item_btn.setProperty("class", "danger")
        self.remove_item_btn.clicked.connect(self.remove_selected_item)
        sel_layout.addWidget(self.remove_item_btn)
        
        item_layout.addLayout(sel_layout)
        
        # Selected Items Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Item Name", "Description", "Current Stock", "Add Quantity", "ID"])
        self.table.setColumnHidden(4, True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # When cells change, invalidate DB log id tracking so user needs to resave
        self.table.cellChanged.connect(self.reset_log_tracking)
        item_layout.addWidget(self.table)
        
        self.main_layout.addWidget(item_group)
        
        # 3. Actions
        btn_layout = QHBoxLayout()
        self.print_btn = QPushButton("🖨️ &Save & Print Form (PDF)")
        self.print_btn.setProperty("class", "secondary")
        self.print_btn.clicked.connect(self.save_and_print_pdf)
        
        self.submit_btn = QPushButton("&Save Stock In" if not self.log_id else "&Update Stock In")
        self.submit_btn.setProperty("class", "primary")
        self.submit_btn.clicked.connect(self.validate_and_submit_only)
        self.submit_btn.setDefault(True)
        
        cancel_btn = QPushButton("&Cancel / Close")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.print_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.submit_btn)
        self.main_layout.addLayout(btn_layout)
        
        # UX: Set initial focus
        self.receiver_input.setFocus()
        
        if self.log_id:
            self.load_log_data()
        elif preselected_items:
            for item in preselected_items:
                self.add_specific_item(item["id"], item["name"], item["desc"])

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

    def refresh_current_stock(self):
        loc_id = self.location_cb.currentData()
        self.table.blockSignals(True)
        with SessionLocal() as session:
            for row in range(self.table.rowCount()):
                item_id = int(self.table.item(row, 4).text())
                stock = session.query(Stock).filter_by(item_id=item_id, location_id=loc_id).first()
                qty = stock.quantity if stock else 0.0
                self.table.setItem(row, 2, QTableWidgetItem(f"{qty:.2f}"))
        self.table.blockSignals(False)

    def add_item_to_list(self):
        item_id = self.item_selector.currentData()
        if not item_id: return
        
        with SessionLocal() as session:
            item = session.query(Item).get(item_id)
            if not item: return
            item_name = item.name
            desc = item.description if item.description else ""
            
        self.add_specific_item(item_id, item_name, desc)

    def add_specific_item(self, item_id, item_name, description):
        # Check if already added
        for r in range(self.table.rowCount()):
            if self.table.item(r, 4).text() == str(item_id):
                return
                
        loc_id = self.location_cb.currentData()
        with SessionLocal() as session:
            stock = session.query(Stock).filter_by(item_id=item_id, location_id=loc_id).first()
            current = stock.quantity if stock else 0.0
            
        self.table.blockSignals(True)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(item_name))
        self.table.setItem(row, 1, QTableWidgetItem(description))
        
        curr_item = QTableWidgetItem(f"{current:.2f}")
        curr_item.setFlags(curr_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 2, curr_item)
        
        add_input = QTableWidgetItem("1.00")
        self.table.setItem(row, 3, add_input)
        
        self.table.setItem(row, 4, QTableWidgetItem(str(item_id)))
        self.table.blockSignals(False)
        self.reset_log_tracking()

    def remove_selected_item(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        self.table.blockSignals(True)
        for index in sorted(selected, reverse=True):
            self.table.removeRow(index.row())
        self.table.blockSignals(False)
        self.reset_log_tracking()

    def load_log_data(self):
        with SessionLocal() as session:
            log = session.query(StockInLog).options(
                joinedload(StockInLog.added_items).joinedload(StockInItem.item)
            ).get(self.log_id)
            
            if log:
                self.date_input.setDate(QDate(log.date.year, log.date.month, log.date.day))
                self.receiver_input.setText(log.received_by)
                self.remarks_input.setText(log.source_remarks or "")
                
                idx = self.location_cb.findData(log.dest_location_id)
                self.location_cb.setCurrentIndex(idx)
                
                self.table.blockSignals(True)
                for si in log.added_items:
                    if not si.item: continue
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    self.table.setItem(row, 0, QTableWidgetItem(si.item.name))
                    self.table.setItem(row, 1, QTableWidgetItem(si.item.description or ""))
                    
                    # Current stock representation (shows current total stock, not historical before-the-fact)
                    stock = session.query(Stock).filter_by(item_id=si.item_id, location_id=log.dest_location_id).first()
                    current = stock.quantity if stock else 0.0
                    
                    curr_item = QTableWidgetItem(f"{current:.2f}")
                    curr_item.setFlags(curr_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row, 2, curr_item)
                    self.table.setItem(row, 3, QTableWidgetItem(f"{si.quantity:.2f}"))
                    self.table.setItem(row, 4, QTableWidgetItem(str(si.item_id)))
                self.table.blockSignals(False)

    def reset_log_tracking(self, *args):
        # We only invalidate new additions; edits to an existing log shouldn't clear its ID but we shouldn't allow simple bypassing of validation
        # Actually it's simple enough to just require Save before Print if forms change
        pass

    def validate_data(self):
        if not self.receiver_input.text().strip():
            raise ValueError("Please enter who received the items.")
        if self.table.rowCount() == 0:
            raise ValueError("Please add at least one item to stock in.")
            
        loc_id = self.location_cb.currentData()
        items_to_add = []
        
        for row in range(self.table.rowCount()):
            item_name = self.table.item(row, 0).text()
            pull_qty_str = self.table.item(row, 3).text()
            try:
                pull_qty = float(pull_qty_str)
            except ValueError:
                raise ValueError(f"Invalid quantity for {item_name}.")
            
            item_id = int(self.table.item(row, 4).text())
            
            if pull_qty <= 0:
                raise ValueError(f"Quantity to add for {item_name} must be greater than zero.")
            
            items_to_add.append({
                "id": item_id,
                "name": item_name,
                "qty": pull_qty
            })
            
        return loc_id, items_to_add

    def submit_to_database(self):
        """Processes the database transaction. Returns True if successful."""
        try:
            loc_id, items_to_add = self.validate_data()
        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
            return False

        with SessionLocal() as session:
            try:
                if self.log_id:
                    # Editing Existing - Reverse logic first
                    old_log = session.query(StockInLog).options(joinedload(StockInLog.added_items)).get(self.log_id)
                    for old_si in old_log.added_items:
                        old_stock = session.query(Stock).filter_by(
                            item_id=old_si.item_id, 
                            location_id=old_log.dest_location_id
                        ).first()
                        if old_stock:
                            old_stock.quantity -= old_si.quantity
                    for old_si in old_log.added_items:
                        session.delete(old_si)
                    log = old_log
                else:
                    log = StockInLog()
                    session.add(log)

                # Update Metadata
                dt = datetime.combine(self.date_input.date().toPyDate(), datetime.now().time())
                log.date = dt
                log.received_by = self.receiver_input.text().strip().upper()
                log.source_remarks = self.remarks_input.text().strip().upper()
                log.dest_location_id = loc_id
                
                session.flush()
                self.db_log_id = log.id

                # Record Items and Add to Inventory
                loc_name = self.location_cb.currentText()
                for clip in items_to_add:
                    s_item = StockInItem(
                        log_id=log.id,
                        item_id=clip["id"],
                        quantity=clip["qty"]
                    )
                    session.add(s_item)
                    
                    # Add to Stock
                    stock = session.query(Stock).filter_by(item_id=clip["id"], location_id=loc_id).first()
                    if not stock: 
                         stock = Stock(item_id=clip["id"], location_id=loc_id, quantity=0.0)
                         session.add(stock)
                    stock.quantity += clip["qty"]
                    
                    # Log to Activity Log
                    action_type = "UPDATED" if self.log_id else "ADDED"
                    prefix = f"Stock In Updated (Log #{log.id})" if self.log_id else "Stock In"
                    
                    log_entry = InventoryActionLog(
                        timestamp=datetime.now(),
                        item_name=clip["name"],
                        action_type=action_type,
                        details=f"{prefix}: +{clip['qty']:.2f} received by {log.received_by}. Source: {log.source_remarks}. New Stock: {stock.quantity:.2f}",
                        user=log.received_by
                    )
                    session.add(log_entry)
                
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to save record: {e}")
                return False

    def validate_and_submit_only(self):
        if self.submit_to_database():
            QMessageBox.information(self, "Success", "Stock In record saved and inventory adjusted.")
            self.accept()

    def save_and_print_pdf(self):
        if not self.submit_to_database():
            return
            
        data = {
            "date": self.date_input.date().toString("yyyy-MM-dd"),
            "receiver": self.receiver_input.text().strip().upper(),
            "remarks": self.remarks_input.text().strip().upper(),
            "location": self.location_cb.currentText().upper(),
        }
        
        items_data = []
        for row in range(self.table.rowCount()):
            items_data.append({
                "name": self.table.item(row, 0).text(),
                "desc": self.table.item(row, 1).text(),
                "qty": self.table.item(row, 3).text()
            })
            
        filename = f"STOCK_IN_{data['receiver'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        
        success, err = generate_stock_in_pdf(data, items_data, filename)
        if success:
            self.accept()
        else:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {err}")

class StockInManager(QWidget):
    """Main view for Stock In logbook."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        
        header = QLabel("Stock In Logbook")
        header.setObjectName("headerTitle")
        self.main_layout.addWidget(header)
        
        self.status_lbl = QLabel("Showing all records")
        self.main_layout.addWidget(self.status_lbl)
        
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("➕ Record Stock In")
        self.add_btn.setProperty("class", "primary")
        self.add_btn.clicked.connect(self.open_add_dialog)
        toolbar.addWidget(self.add_btn)
        
        self.delete_btn = QPushButton("🗑 Delete Selected")
        self.delete_btn.setProperty("class", "danger")
        self.delete_btn.clicked.connect(self.delete_selected_logs)
        toolbar.addWidget(self.delete_btn)
        
        toolbar.addStretch()
        
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self.load_logs)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter logs by receiver, remarks, or item...")
        self.search_input.setFixedWidth(300)
        self.search_input.textChanged.connect(self.search_timer.start)
        
        # Initialize Completer
        self.search_completer = QCompleter(self)
        self.search_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.search_input.setCompleter(self.search_completer)
        
        toolbar.addWidget(self.search_input)
        
        self.main_layout.addLayout(toolbar)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Date", "Received By", "Items Added", "Destination", "Remarks/Source", "ID"])
        self.table.setColumnHidden(5, True)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self.edit_log)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.main_layout.addWidget(self.table)
        
        self.load_logs()

    def show_context_menu(self, position):
        menu = QMenu()
        reprint_action = menu.addAction("🖨️ Re-print Confirmation")
        
        action = menu.exec(self.table.mapToGlobal(position))
        if action == reprint_action:
            self.reprint_log()

    def reprint_log(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
             QMessageBox.warning(self, "No Selection", "Please select a log to reprint.")
             return
        
        row = selected_rows[0].row()
        log_id = int(self.table.item(row, 5).text())
        
        with SessionLocal() as session:
            log = session.query(StockInLog).options(
                joinedload(StockInLog.added_items).joinedload(StockInItem.item),
                joinedload(StockInLog.dest_location)
            ).get(log_id)
            
            if not log:
                return
                
            data = {
                "date": log.date.strftime("%Y-%m-%d"),
                "receiver": log.received_by,
                "remarks": log.source_remarks or "",
                "location": log.dest_location.name if log.dest_location else "",
            }
            
            items_data = []
            for si in log.added_items:
                if not si.item: continue
                items_data.append({
                    "name": si.item.name,
                    "desc": si.item.description or "",
                    "qty": f"{si.quantity:.2f}"
                })
                
            filename = f"STOCK_IN_{data['receiver'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            success, err = generate_stock_in_pdf(data, items_data, filename)
            
            if not success:
                QMessageBox.critical(self, "Error", f"Failed to generate PDF: {err}")

    def open_add_dialog(self):
        d = StockInEntryDialog(None, self)
        if d.exec():
            self.load_logs()

    def edit_log(self, row, col):
        log_id = int(self.table.item(row, 5).text())
        d = StockInEntryDialog(log_id, self)
        if d.exec():
            self.load_logs()

    def delete_selected_logs(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
             QMessageBox.warning(self, "No Selection", "Please select logs to delete.")
             return
        
        reply = QMessageBox.question(self, "Confirm Delete", 
                                   f"Are you sure you want to delete {len(selected_rows)} record(s)?\n\nStock levels will be reversed (deducted!).",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            with SessionLocal() as session:
                try:
                    for row_proxy in selected_rows:
                        log_id = int(self.table.item(row_proxy.row(), 5).text())
                        log = session.query(StockInLog).options(joinedload(StockInLog.added_items)).get(log_id)
                        if log:
                            for si in log.added_items:
                                stock = session.query(Stock).filter_by(item_id=si.item_id, location_id=log.dest_location_id).first()
                                if stock:
                                    stock.quantity -= si.quantity
                            session.delete(log)
                    session.commit()
                    self.load_logs()
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Error", f"Deletion failed: {e}")

    def update_completer(self, session):
        """Populates the search completer with item names and receivers."""
        # 1. Fetch item names (Name - Description format)
        items = session.query(Item.name, Item.description).all()
        item_strings = []
        for name, desc in items:
            s = name
            if desc:
                s += f" - {desc}"
            item_strings.append(s)
            
        # 2. Fetch unique receivers
        receivers = session.query(StockInLog.received_by).distinct().all()
        receiver_strings = [r[0] for r in receivers if r[0]]
        
        # 3. Combine and set model
        all_options = sorted(list(set(item_strings + receiver_strings)))
        self.search_completer.setModel(QStringListModel(all_options))

    def load_logs(self):
        search = self.search_input.text().strip().upper()
        with SessionLocal() as session:
            query = session.query(StockInLog).options(
                joinedload(StockInLog.added_items).joinedload(StockInItem.item),
                joinedload(StockInLog.dest_location)
            ).order_by(StockInLog.date.desc())
            
            if search:
                # Refined filtering to support "Name - Description" format and case-insensitive matching
                query = query.join(StockInLog.dest_location).filter(
                    (StockInLog.received_by.ilike(f"%{search}%")) |
                    (StockInLog.source_remarks.ilike(f"%{search}%")) |
                    (Location.name.ilike(f"%{search}%")) |
                    (StockInLog.added_items.any(
                        StockInItem.item.has(
                            (Item.name.ilike(f"%{search}%")) |
                            (Item.description.ilike(f"%{search}%")) |
                            ((Item.name + " - " + func.coalesce(Item.description, "")).ilike(f"%{search}%"))
                        )
                    ))
                ).distinct()
            
            logs = query.all()
            
            # Update Completer with latest items and receivers
            self.update_completer(session)
            
            self.table.setRowCount(len(logs))
            if len(logs) == 0:
                self.status_lbl.setText("No records found matching your search.")
            else:
                self.status_lbl.setText(f"Showing {len(logs)} stock in records")
                
            for i, log in enumerate(logs):
                self.table.setItem(i, 0, QTableWidgetItem(log.date.strftime("%Y-%m-%d %H:%M")))
                self.table.setItem(i, 1, QTableWidgetItem(log.received_by))
                
                items_list = []
                for si in log.added_items:
                    if not si.item:
                        items_list.append(f"Deleted Item (+{si.quantity:.2f})")
                        continue
                    summary = f"{si.item.name}"
                    if si.item.description:
                         summary += f" - {si.item.description}"
                    summary += f" (+{si.quantity:.2f})"
                    items_list.append(summary)
                
                items_summary = ", ".join(items_list)
                self.table.setItem(i, 2, QTableWidgetItem(items_summary))
                self.table.setItem(i, 3, QTableWidgetItem(log.dest_location.name if log.dest_location else ""))
                self.table.setItem(i, 4, QTableWidgetItem(log.source_remarks))
                self.table.setItem(i, 5, QTableWidgetItem(str(log.id)))
