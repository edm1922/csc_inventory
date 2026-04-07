import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, 
                             QHeaderView, QGroupBox, QFormLayout, QDialog, QComboBox, QAbstractItemView,
                             QMenu, QListWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator, QColor

from core.database import SessionLocal, Item, Supplier, Location, Stock, InventoryActionLog
from core.config import get_thresholds, save_thresholds, get_effective_threshold
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from exporter import generate_inventory_checklist, generate_stock_confirmation_word
from core.excel_generator import generate_excel_report
from datetime import datetime
import os
from PyQt6.QtCore import Qt, QTimer

class ThresholdSettingsDialog(QDialog):
    """Dialog to edit global stock threshold settings."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Threshold Settings")
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.pcs_input = QLineEdit()
        self.pcs_input.setValidator(QDoubleValidator(0.0, 10000.0, 2))
        
        self.box_input = QLineEdit()
        self.box_input.setValidator(QDoubleValidator(0.0, 10000.0, 2))
        
        form.addRow("Default Pieces (PCS) Threshold:", self.pcs_input)
        form.addRow("Default for Other Units (BOX, ROLL, etc.):", self.box_input)
        
        layout.addLayout(form)
        
        # Load current values
        t = get_thresholds()
        self.pcs_input.setText(str(t.get("pcs_threshold", 50.0)))
        self.box_input.setText(str(t.get("box_threshold", 10.0)))
        
        btns = QHBoxLayout()
        save_btn = QPushButton("&Save Defaults")
        save_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setDefault(True)
        cancel_btn = QPushButton("&Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
        
        # UX: Set focus to first input
        self.pcs_input.setFocus()
        
    def save_settings(self):
        try:
            pcs = float(self.pcs_input.text() or 50.0)
            box = float(self.box_input.text() or 10.0)
            if pcs < 0 or box < 0:
                raise ValueError("Thresholds must be positive.")
            save_thresholds(pcs, box)
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))

class EditItemDialog(QDialog):
    """Dialog to add or edit an inventory item and its supplier."""
    def __init__(self, item_id=None, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.setWindowTitle("Add New Item" if not item_id else "Edit Item Details")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        # Item Details
        self.name_input = QLineEdit()
        self.desc_input = QLineEdit()
        self.unit_input = QComboBox()
        self.unit_input.setEditable(True)
        self.unit_input.addItems(["PCS", "BOX", "ROLL", "REAM", "BOT", "PACK"])
        
        self.price_input = QLineEdit()
        self.price_input.setValidator(QDoubleValidator(0.0, 100000.0, 2))
        
        self.threshold_input = QLineEdit()
        self.threshold_input.setValidator(QDoubleValidator(0.0, 10000.0, 2))
        self.threshold_input.setPlaceholderText("0.00 for Default")
        
        self.act_stock_input = QLineEdit()
        self.act_stock_input.setValidator(QDoubleValidator(0.0, 10000.0, 2))
        
        self.pending_input = QLineEdit()
        # Non-editable, calculated
        self.pending_input.setReadOnly(True)
        self.pending_input.setStyleSheet("background-color: #f0f0f0; color: #555;")
        
        # Threshold Hint
        self.threshold_hint = QLabel("Needs Restock when stock ≤ 50% of threshold")
        self.threshold_hint.setStyleSheet("color: #7f8c8d; font-size: 11px; font-style: italic;")
        
        # Connect signals for automatic calculation
        self.threshold_input.textChanged.connect(self.update_pending_order)
        self.act_stock_input.textChanged.connect(self.update_pending_order)
        self.unit_input.currentTextChanged.connect(self.update_pending_order)
        
        # Location Selection
        self.location_input = QComboBox()
        self.location_input.setEditable(False)
        
        form.addRow("Item Name:", self.name_input)
        form.addRow("Description:", self.desc_input)
        form.addRow("Unit:", self.unit_input)
        form.addRow("Price:", self.price_input)
        form.addRow("Threshold (Override):", self.threshold_input)
        form.addRow("", self.threshold_hint)
        form.addRow("Actual Stock:", self.act_stock_input)
        form.addRow("Location for Stock:", self.location_input)
        form.addRow("Pending Order (Auto):", self.pending_input)
        
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        self.save_btn = QPushButton("&Save")
        self.save_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.save_btn.clicked.connect(self.accept)
        self.save_btn.setDefault(True)
        self.cancel_btn = QPushButton("&Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btns.addWidget(self.save_btn)
        btns.addWidget(self.cancel_btn)
        layout.addLayout(btns)
        
        # UX: Set initial focus
        self.name_input.setFocus()
        
        self.load_locations()
        if self.item_id:
            self.load_item_data()

    def update_pending_order(self):
        try:
            custom_t = float(self.threshold_input.text() or 0.0)
            unit = self.unit_input.currentText()
            effective_t, is_custom = get_effective_threshold(unit, custom_t)
            
            if is_custom:
                self.threshold_hint.setText(f"Custom Override: {effective_t} (Restock at {effective_t/2:.1f})")
                self.threshold_hint.setStyleSheet("color: #e67e22; font-size: 11px; font-weight: bold;")
            else:
                self.threshold_hint.setText(f"Global Default: {effective_t} (Restock at {effective_t/2:.1f})")
                self.threshold_hint.setStyleSheet("color: #7f8c8d; font-size: 11px; font-style: italic;")
            
            actual = float(self.act_stock_input.text() or 0.0)
            pending = max(0.0, effective_t - actual)
            self.pending_input.setText(f"{pending:.2f}")
        except ValueError:
            self.pending_input.setText("0.00")

    def load_locations(self):
        with SessionLocal() as session:
            locations = session.query(Location).all()
            for loc in locations:
                self.location_input.addItem(loc.name, loc.id)

    def load_item_data(self):
        with SessionLocal() as session:
            item = session.query(Item).options(joinedload(Item.supplier)).get(self.item_id)
            if item:
                self.name_input.setText(item.name)
                self.desc_input.setText(item.description or "")
                self.unit_input.setCurrentText(item.unit or "")
                self.price_input.setText(str(item.price))
                self.threshold_input.setText(str(item.standard_stock))
                # Initial pending update call though textChanged will trigger it
                self.update_pending_order()
                
                # Load stock for the currently selected location in dialog
                self.update_stock_display()
                self.location_input.currentIndexChanged.connect(self.update_stock_display)

    def update_stock_display(self):
        if not self.item_id: return
        loc_id = self.location_input.currentData()
        with SessionLocal() as session:
            stock = session.query(Stock).filter_by(item_id=self.item_id, location_id=loc_id).first()
            self.act_stock_input.setText(str(stock.quantity if stock else 0.0))

    def get_data(self):
        return {
            "name": self.name_input.text().strip().upper(),
            "description": self.desc_input.text().strip().upper(),
            "unit": self.unit_input.currentText().strip().upper(),
            "price": float(self.price_input.text() or 0.0),
            "threshold": float(self.threshold_input.text() or 0.0),
            "act_stock": float(self.act_stock_input.text() or 0.0),
            "location_id": self.location_input.currentData(),
            "pending": float(self.pending_input.text() or 0.0)
        }


class LocationManagerDialog(QDialog):
    """Dialog to manage inventory locations."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Locations")
        self.setMinimumSize(400, 350)
        
        layout = QVBoxLayout(self)
        
        # Add New Location Section
        add_group = QGroupBox("Add New Location")
        add_layout = QHBoxLayout(add_group)
        self.new_loc_input = QLineEdit()
        self.new_loc_input.setPlaceholderText("Enter location name...")
        self.add_btn = QPushButton("Add")
        self.add_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.add_btn.clicked.connect(self.add_location)
        add_layout.addWidget(self.new_loc_input)
        add_layout.addWidget(self.add_btn)
        layout.addWidget(add_group)
        
        # Existing Locations List
        layout.addWidget(QLabel("Existing Locations:"))
        self.loc_list = QListWidget()
        self.loc_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.loc_list)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        self.edit_btn = QPushButton("&Edit Selected")
        self.edit_btn.clicked.connect(self.edit_location)
        self.delete_btn = QPushButton("&Delete Selected")
        self.delete_btn.setStyleSheet("background-color: #c0392b; color: white;")
        self.delete_btn.clicked.connect(self.delete_location)
        self.close_btn = QPushButton("&Close")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setDefault(True)
        
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        
        self.load_locations()
        
    def load_locations(self):
        self.loc_list.clear()
        with SessionLocal() as session:
            locations = session.query(Location).order_by(Location.name).all()
            for loc in locations:
                self.loc_list.addItem(loc.name)
                
    def add_location(self):
        name = self.new_loc_input.text().strip().title()
        if not name:
            QMessageBox.warning(self, "Invalid Input", "Location name cannot be empty.")
            return
            
        with SessionLocal() as session:
            existing = session.query(Location).filter(func.lower(Location.name) == name.lower()).first()
            if existing:
                QMessageBox.warning(self, "Duplicate", f"Location '{name}' already exists.")
                return
                
            new_loc = Location(name=name)
            session.add(new_loc)
            session.commit()
            self.new_loc_input.clear()
            self.load_locations()
            
    def edit_location(self):
        item = self.loc_list.currentItem()
        if not item: return
        
        old_name = item.text()
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "Edit Location", "Update location name:", text=old_name)
        
        if ok and new_name.strip():
            new_name = new_name.strip().title()
            with SessionLocal() as session:
                loc = session.query(Location).filter_by(name=old_name).first()
                if loc:
                    # Check if new name already exists elsewhere
                    existing = session.query(Location).filter(func.lower(Location.name) == new_name.lower(), Location.id != loc.id).first()
                    if existing:
                        QMessageBox.warning(self, "Duplicate", f"Location '{new_name}' already exists.")
                        return
                    loc.name = new_name
                    session.commit()
                    self.load_locations()
                    
    def delete_location(self):
        item = self.loc_list.currentItem()
        if not item: return
        
        name = item.text()
        reply = QMessageBox.question(self, "Confirm Delete", 
                                   f"Are you sure you want to delete '{name}'?\n\n"
                                   "This will fail if any stock is associated with this location.",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            with SessionLocal() as session:
                loc = session.query(Location).filter_by(name=name).first()
                if loc:
                    # Check for dependencies
                    if loc.stocks:
                        QMessageBox.warning(self, "Action Denied", "Cannot delete location with existing stock. Remove all items from this location first.")
                        return
                    session.delete(loc)
                    session.commit()
                    self.load_locations()


class InventoryManager(QWidget):
    """Main Inventory Management view."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Supplies Inventory Management")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #1F4E78; margin-bottom: 2px;")
        self.main_layout.addWidget(header)
        
        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet("color: #7f8c8d; font-size: 11px; margin-bottom: 10px;")
        self.main_layout.addWidget(self.status_lbl)
        
        # Filter Bar
        # Search Debounce Timer
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300) # Wait 300ms until user stops typing
        self.search_timer.timeout.connect(self.load_data)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Item or Description...")
        self.search_input.textChanged.connect(self.search_timer.start)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(self.search_input)
        
        filter_layout.addWidget(QLabel("Location:"))
        self.location_filter = QComboBox()
        self.location_filter.addItem("ALL LOCATIONS", None)
        self.load_filter_locations()
        self.location_filter.currentIndexChanged.connect(self.load_data)
        filter_layout.addWidget(self.location_filter)
        
        self.add_btn = QPushButton("+ Add New Item")
        self.add_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.add_btn.clicked.connect(self.add_item)
        filter_layout.addWidget(self.add_btn)
        
        self.print_btn = QPushButton("🖨️ Print / Export")
        self.print_btn.setStyleSheet("padding: 8px; background-color: #2980b9; color: white; font-weight: bold; border-radius: 4px;")
        self.print_btn.clicked.connect(self.open_print_menu)
        filter_layout.addWidget(self.print_btn)
        
        self.delete_btn = QPushButton("🗑 Delete Selected")
        self.delete_btn.setStyleSheet("background-color: #c0392b; color: white;")
        self.delete_btn.clicked.connect(self.delete_selected_item)
        filter_layout.addWidget(self.delete_btn)
        
        self.settings_btn = QPushButton("⚙️ Thresholds")
        self.settings_btn.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold;")
        self.settings_btn.clicked.connect(self.open_threshold_settings)
        filter_layout.addWidget(self.settings_btn)
        
        self.manage_loc_btn = QPushButton("📍 Manage Locations")
        self.manage_loc_btn.setStyleSheet("background-color: #34495e; color: white; font-weight: bold;")
        self.manage_loc_btn.clicked.connect(self.open_location_manager)
        filter_layout.addWidget(self.manage_loc_btn)
        
        self.main_layout.addLayout(filter_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Item", "Description", "Unit", "Price", 
            "Threshold", "Actual", "Location", "ID"
        ])
        self.table.setColumnHidden(7, True) # ID column
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.cellDoubleClicked.connect(self.edit_item)
        self.main_layout.addWidget(self.table)
        
        self.load_data()

    def load_filter_locations(self):
        current_data = self.location_filter.currentData()
        self.location_filter.blockSignals(True)
        self.location_filter.clear()
        self.location_filter.addItem("ALL LOCATIONS", None)
        with SessionLocal() as session:
            locations = session.query(Location).order_by(Location.name).all()
            for loc in locations:
                self.location_filter.addItem(loc.name, loc.id)
        
        # Restore selection
        index = self.location_filter.findData(current_data)
        if index >= 0:
            self.location_filter.setCurrentIndex(index)
        self.location_filter.blockSignals(False)

    def load_data(self):
        search = self.search_input.text().strip().upper()
        loc_filter_id = self.location_filter.currentData()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        with SessionLocal() as session:
            # We want to show items and their stock at specific locations
            query = session.query(Item).options(joinedload(Item.supplier), joinedload(Item.stocks).joinedload(Stock.location))
            if search:
                query = query.filter(
                    (Item.name.like(f"%{search}%")) | (Item.description.like(f"%{search}%"))
                )
            
            items = query.all()
            
            # Flatten data if location filter is active, otherwise show multi-rows or sum
            display_rows = []
            for item in items:
                if loc_filter_id:
                    # Show only if there is a stock record for this location
                    s = next((s for s in item.stocks if s.location_id == loc_filter_id), None)
                    if s:
                        display_rows.append((item, s.quantity, s.location.name))
                    # Removed the 'else' that was adding 0.0 rows for every item
                else:
                    # Show all locations for this item
                    if not item.stocks:
                        display_rows.append((item, 0.0, "N/A"))
                    for s in item.stocks:
                        display_rows.append((item, s.quantity, s.location.name))

            self.table.setRowCount(len(display_rows))
            
            for i, (item, stock_qty, loc_name) in enumerate(display_rows):
                eff_threshold, is_custom = get_effective_threshold(item.unit, item.standard_stock)
                
                self.table.setItem(i, 0, QTableWidgetItem(item.name))
                self.table.setItem(i, 1, QTableWidgetItem(item.description or ""))
                self.table.setItem(i, 2, QTableWidgetItem(item.unit or ""))
                self.table.setItem(i, 3, QTableWidgetItem(f"P{item.price:.2f}"))
                
                t_item = QTableWidgetItem(f"{eff_threshold} {'(C)' if is_custom else '(D)'}")
                if is_custom:
                    t_item.setForeground(QColor("#e67e22"))
                    t_item.setToolTip("Custom Threshold Override")
                else:
                    t_item.setForeground(QColor("#7f8c8d"))
                    t_item.setToolTip("System Default Threshold")
                
                self.table.setItem(i, 4, t_item)
                self.table.setItem(i, 5, QTableWidgetItem(str(stock_qty)))
                self.table.setItem(i, 6, QTableWidgetItem(loc_name))
                self.table.setItem(i, 7, QTableWidgetItem(str(item.id)))

            self.table.setSortingEnabled(True)
            self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
            
            # UX: Update status label
            if len(display_rows) == 0:
                self.status_lbl.setText("No items found matching your filters.")
                self.status_lbl.setStyleSheet("color: #c0392b; font-weight: bold; font-size: 11px; margin-bottom: 10px;")
            else:
                self.status_lbl.setText(f"Showing {len(display_rows)} item/location records")
                self.status_lbl.setStyleSheet("color: #7f8c8d; font-size: 11px; margin-bottom: 10px;")

    def add_item(self):
        dialog = EditItemDialog(parent=self)
        # Pre-select based on current filter
        loc_id = self.location_filter.currentData()
        if loc_id:
            index = dialog.location_input.findData(loc_id)
            if index >= 0:
                dialog.location_input.setCurrentIndex(index)
                
        if dialog.exec():
            data = dialog.get_data()
            self.save_item(None, data)

    def edit_item(self, row, col):
        id_item = self.table.item(row, 7)
        if not id_item: return
        item_id = int(id_item.text())
        dialog = EditItemDialog(item_id, self)
        
        # Pre-select the location from the table row
        current_loc_name = self.table.item(row, 6).text()
        index = dialog.location_input.findText(current_loc_name)
        if index >= 0:
            dialog.location_input.setCurrentIndex(index)
            dialog.update_stock_display() # Force load for this location
            
        if dialog.exec():
            data = dialog.get_data()
            self.save_item(item_id, data)

    def save_item(self, item_id, data):
        with SessionLocal() as session:
            try:
                # Supplier handling removed from UI, keeping simplified logic
                supplier = None
                
                if item_id:
                    item = session.query(Item).get(item_id)
                    # CHECK FOR NAME CONFLICT with ANOTHER ID (matching both name and description)
                    duplicate = session.query(Item).filter(
                        func.upper(Item.name) == data["name"].upper(),
                        func.upper(Item.description) == data["description"].upper(),
                        Item.id != item_id
                    ).first()
                    if duplicate:
                        QMessageBox.warning(self, "Item Conflict", 
                                           f"An item with the name '{data['name']}' and the same description already exists (ID: {duplicate.id}).\n\n"
                                           "Please ensure either the name or description is unique.")
                        return
                    loc_id = data["location_id"]
                else:
                    # IMPROVED: Check if an item with BOTH the same name and description already exists
                    item = session.query(Item).filter(
                        func.upper(Item.name) == data["name"].upper(),
                        func.upper(Item.description) == data["description"].upper()
                    ).first()
                    loc_id = data["location_id"]
                    
                    if item:
                        # Item exists, check if it already has stock for THIS location
                        existing_stock = session.query(Stock).filter_by(item_id=item.id, location_id=loc_id).first()
                        if existing_stock:
                            QMessageBox.warning(self, "Item Already Exists", 
                                               f"'{data['name']}' with this description already has a record for this location.\n\n"
                                               "Please find and edit the existing entry in the table.")
                            return
                        # If no stock for this location, we proceed using the existing item object
                        # We will create the stock record at the flush/commit stage below
                    else:
                        # Brand new item definition
                        item = Item()
                        session.add(item)
                
                # Update Item Meta (Name, Unit, etc.)
                item.name = data["name"]
                item.description = data["description"]
                item.unit = data["unit"]
                item.price = data["price"]
                item.standard_stock = data["threshold"]
                item.pending_order = data["pending"]
                
                # Update stock for specific location
                session.flush() # Ensure we have item.id (especially for brand new items)
                
                stock = session.query(Stock).filter_by(item_id=item.id, location_id=loc_id).first()
                loc_name = session.query(Location.name).filter_by(id=loc_id).scalar() or "Unknown"
                
                if not stock:
                     # Create new stock record for this location
                     stock = Stock(item_id=item.id, location_id=loc_id, quantity=data["act_stock"])
                     session.add(stock)
                     # LOG ADDED
                     log = InventoryActionLog(
                         item_name=item.name,
                         action_type="ADDED",
                         details=f"Initial Qty: {data['act_stock']} at {loc_name}"
                     )
                     session.add(log)
                else:
                    # Update existing stock for this location
                    old_qty = stock.quantity
                    new_qty = data["act_stock"]
                    stock.quantity = new_qty
                    
                    # LOG UPDATED (if qty changed or if item was JUST created but stock existed?)
                    # Actually, if we're here, it's an update.
                    if old_qty != new_qty:
                        log = InventoryActionLog(
                            item_name=item.name,
                            action_type="UPDATED",
                            details=f"Qty: {old_qty} -> {new_qty} at {loc_name}"
                        )
                        session.add(log)
                    else:
                        # General update (price, threshold etc)
                        log = InventoryActionLog(
                            item_name=item.name,
                            action_type="UPDATED",
                            details=f"Item details updated at {loc_name}"
                        )
                        session.add(log)

                session.commit()
                self.load_data()
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to save item: {str(e)}")

    def open_threshold_settings(self):
        dialog = ThresholdSettingsDialog(self)
        if dialog.exec():
            self.load_data() # Refresh table to show new defaults if applicable

    def delete_selected_item(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select at least one item to delete.")
            return
        
        num_items = len(selected_rows)
        item_names = [self.table.item(row.row(), 0).text() for row in selected_rows]
        
        if num_items == 1:
            msg = f"Are you sure you want to delete '{item_names[0]}'?"
        else:
            msg = f"Are you sure you want to delete these {num_items} items?"
            
        reply = QMessageBox.question(self, "Confirm Delete", 
                                   f"{msg}\n\nThis will permanently remove all linked records (Stock, Request History).",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            with SessionLocal() as session:
                try:
                    for row_proxy in selected_rows:
                        item_id = int(self.table.item(row_proxy.row(), 7).text())
                        item = session.query(Item).get(item_id)
                        if item:
                            # LOG REMOVED
                            log = InventoryActionLog(
                                item_name=item.name,
                                action_type="REMOVED",
                                details="Item and all linked stock removed"
                            )
                            session.add(log)
                            session.delete(item)
                    
                    session.commit()
                    self.load_data()
                    QMessageBox.information(self, "Deleted", f"Successfully removed {num_items} items.")
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Error", f"Failed to delete items: {str(e)}")

    def open_location_manager(self):
        dialog = LocationManagerDialog(self)
        if dialog.exec():
            # Refresh all location dropdowns in this module
            self.load_filter_locations()
            self.load_data()

    def open_print_menu(self):
        """Shows a menu to choose between Excel checklist or Word report."""
        menu = QMenu(self)
        excel_action = menu.addAction("📊 Excel (Checklist)")
        word_action = menu.addAction("📄 Word (Confirmation Report)")
        raw_excel_action = menu.addAction("📈 Raw Excel Export")
        
        # Style the menu slightly
        menu.setStyleSheet("""
            QMenu { background-color: white; border: 1px solid #bdc3c7; }
            QMenu::item { padding: 8px 25px; color: black; }
            QMenu::item:selected { background-color: #3498db; color: white; }
        """)
        
        # Position the menu below the button
        action = menu.exec(self.print_btn.mapToGlobal(self.print_btn.rect().bottomLeft()))
        
        if action == excel_action:
            self.export_selected("excel")
        elif action == word_action:
            self.export_selected("word")
        elif action == raw_excel_action:
            self.export_selected("raw_excel")

    def export_selected(self, format_type):
        """Processes selection and generates the requested document."""
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            QMessageBox.warning(self, "No Selection", "Please select items in the table to print.")
            return

        # Gather selected row indices
        selected_rows = set()
        for r in selected_ranges:
            for row in range(r.topRow(), r.bottomRow() + 1):
                selected_rows.add(row)

        data_rows = []
        for row in sorted(list(selected_rows)):
            if self.table.isRowHidden(row):
                continue
                
            item_name = self.table.item(row, 0).text()
            unit = self.table.item(row, 2).text()
            price_text = self.table.item(row, 3).text().replace('P', '').replace(',', '')
            # Extract threshold value from string like "10.0 (D)"
            threshold_text = self.table.item(row, 4).text().split(' ')[0]
            actual = self.table.item(row, 5).text()
            location = self.table.item(row, 6).text()
            
            data_rows.append({
                "Item": item_name,
                "Threshold": threshold_text,
                "Actual": float(actual) if actual else 0.0,
                "Price": float(price_text) if price_text else 0.0,
                "Unit": unit,
                "Location": location
            })

        if not data_rows:
            QMessageBox.warning(self, "No Data", "No visible data found in selection.")
            return

        location_name = self.location_filter.currentText()
        
        try:
            if format_type == "excel":
                filename = generate_inventory_checklist(data_rows, location_name)
                msg = f"Excel Checklist generated: {filename}"
            elif format_type == "word":
                filename = generate_stock_confirmation_word(data_rows, location_name)
                msg = f"Word Confirmation Report generated: {filename}"
            else:
                # Raw Excel Export using new utility
                headers = ["Item Name", "Description", "Unit", "Price", "Threshold", "Actual Stock", "Location"]
                raw_data = [[r["Item"], "", r["Unit"], r["Price"], r["Threshold"], r["Actual"], r["Location"]] for r in data_rows]
                # Note: table_data above needs to match data_rows structure
                # Let's fix the raw_data mapping
                raw_data = []
                for r in data_rows:
                    raw_data.append([r["Item"], "", r["Unit"], r["Price"], r["Threshold"], r["Actual"], r["Location"]])
                
                filename = f"inventory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                filepath = generate_excel_report("Inventory Export", headers, raw_data, filename)
                os.startfile(filepath)
                QMessageBox.information(self, "Success", f"Excel export generated: {filename}")
                return
            
            # Open the file automatically
            os.startfile(filename) if sys.platform == "win32" else None
            QMessageBox.information(self, "Success", f"{msg}\nOpening file...")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate report: {e}")

    def print_checklist(self):
        # Redirect to the new menu
        self.open_print_menu()

