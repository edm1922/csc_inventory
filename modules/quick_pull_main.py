import os
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, 
                             QHeaderView, QGroupBox, QFormLayout, QDialog, QComboBox, 
                             QDateEdit, QAbstractItemView)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor

from core.database import SessionLocal, Item, Location, Stock, QuickPullLog, QuickPullItem
from sqlalchemy.orm import joinedload

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
        self.purpose_input.setPlaceholderText("Reason for release")
        
        self.destination_input = QLineEdit()
        self.destination_input.setPlaceholderText("Company or Agency destination")
        
        self.location_cb = QComboBox()
        self.load_locations()
        self.location_cb.currentIndexChanged.connect(self.refresh_available_stock)
        
        info_layout.addRow("Date:", self.date_input)
        info_layout.addRow("Requested By:", self.requester_input)
        info_layout.addRow("Purpose:", self.purpose_input)
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
        
        item_layout.addLayout(sel_layout)
        
        # Selected Items Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Item Name", "Description", "Available", "Pull Quantity", "ID"])
        self.table.setColumnHidden(4, True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("QTableWidget { background: white; color: black; }")
        item_layout.addWidget(self.table)
        
        self.main_layout.addWidget(item_group)
        
        # 3. Actions
        btn_layout = QHBoxLayout()
        self.submit_btn = QPushButton("✅ Confirm and Deduct Inventory" if not log_id else "💾 Update and Adjust Inventory")
        self.submit_btn.setStyleSheet("padding: 10px; background-color: #2980b9; color: white; font-weight: bold; font-size: 14px;")
        self.submit_btn.clicked.connect(self.validate_and_submit)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.submit_btn)
        self.main_layout.addLayout(btn_layout)
        
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
                
                session.commit()
                QMessageBox.information(self, "Success", "Record saved and inventory adjusted.")
                self.accept()
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to save record: {e}")

class QuickPullManager(QWidget):
    """Main view for Quick Pull logbook."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Quick Pull Logbook")
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50; margin-bottom: 10px;")
        self.main_layout.addWidget(header)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("➕ Record New Release (Pull)")
        self.add_btn.setStyleSheet("padding: 10px; background-color: #27ae60; color: white; font-weight: bold; border-radius: 5px;")
        self.add_btn.clicked.connect(self.open_add_dialog)
        toolbar.addWidget(self.add_btn)
        
        self.delete_btn = QPushButton("🗑 Delete Selected")
        self.delete_btn.setStyleSheet("padding: 10px; background-color: #c0392b; color: white; font-weight: bold; border-radius: 5px;")
        self.delete_btn.clicked.connect(self.delete_selected_logs)
        toolbar.addWidget(self.delete_btn)
        
        toolbar.addStretch()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter logs by requester, purpose, or item...")
        self.search_input.setFixedWidth(300)
        self.search_input.textChanged.connect(self.load_logs)
        toolbar.addWidget(self.search_input)
        
        self.main_layout.addLayout(toolbar)
        
        # Log Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Date", "Requested By", "Items Pulled", "Location", "Purpose", "Destination", "ID"])
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
                # Basic filtering by requester, purpose, or location
                # For comprehensive item search, we'd need more complex joining
                query = query.filter(
                    (QuickPullLog.requested_by.contains(search)) |
                    (QuickPullLog.purpose.contains(search)) |
                    (QuickPullLog.destination.contains(search))
                )
            
            logs = query.all()
            
            self.table.setRowCount(len(logs))
            for i, log in enumerate(logs):
                self.table.setItem(i, 0, QTableWidgetItem(log.date.strftime("%Y-%m-%d %H:%M")))
                self.table.setItem(i, 1, QTableWidgetItem(log.requested_by))
                
                # Format items summary: "Item A - Description (5), Item B (2)"
                items_list = []
                for pi in log.pulled_items:
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
