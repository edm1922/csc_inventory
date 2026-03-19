import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, 
                             QHeaderView, QGroupBox, QFormLayout, QDialog, QDateEdit,
                             QAbstractItemView)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QDoubleValidator

from database import SessionLocal, PurchaseRequest, PurchaseItem
from sqlalchemy.orm import joinedload
from datetime import datetime

class PurchaseRequestDialog(QDialog):
    def __init__(self, pr_id=None, parent=None):
        super().__init__(parent)
        self.pr_id = pr_id
        self.setWindowTitle("Create Purchase Request" if not pr_id else "Edit Purchase Request")
        self.setMinimumSize(900, 600)
        
        self.main_layout = QVBoxLayout(self)
        
        # Header Info
        header_group = QGroupBox("Request Metadata")
        header_layout = QFormLayout(header_group)
        
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        
        self.pr_no_input = QLineEdit()
        self.pr_no_input.setPlaceholderText("e.g., 000001")
        
        self.dept_input = QLineEdit()
        self.dept_input.setText("OFFICE")
        
        self.end_user_input = QLineEdit()
        self.end_user_input.setText("OFFICE")
        
        self.position_input = QLineEdit()
        
        header_layout.addRow("Date:", self.date_input)
        header_layout.addRow("PR No.:", self.pr_no_input)
        header_layout.addRow("Department:", self.dept_input)
        header_layout.addRow("End-User:", self.end_user_input)
        header_layout.addRow("Position:", self.position_input)
        
        self.main_layout.addWidget(header_group)
        
        # Items Table
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(7)
        self.items_table.setHorizontalHeaderLabels([
            "Item Description", "Purpose / Reason", "For (Dept/End-User)", 
            "Price", "QTY", "Unit", "Total"
        ])
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.items_table.itemChanged.connect(self.calculate_row_total)
        self.main_layout.addWidget(self.items_table)
        
        # Tools
        tool_layout = QHBoxLayout()
        self.add_row_btn = QPushButton("+ Add Item")
        self.add_row_btn.clicked.connect(self.add_blank_row)
        self.remove_row_btn = QPushButton("- Remove Selected")
        self.remove_row_btn.clicked.connect(self.remove_selected_row)
        tool_layout.addWidget(self.add_row_btn)
        tool_layout.addWidget(self.remove_row_btn)
        tool_layout.addStretch()
        
        self.total_label = QLabel("Estimated Total: Php. 0.00")
        self.total_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1F4E78;")
        tool_layout.addWidget(self.total_label)
        self.main_layout.addLayout(tool_layout)
        
        # Signatures
        sig_group = QGroupBox("Signatures")
        sig_layout = QHBoxLayout(sig_group)
        self.prepared_by_input = QLineEdit()
        self.prepared_by_input.setPlaceholderText("Prepared By")
        self.approved_by_input = QLineEdit()
        self.approved_by_input.setPlaceholderText("Approved By")
        sig_layout.addWidget(QLabel("Prepared By:"))
        sig_layout.addWidget(self.prepared_by_input)
        sig_layout.addWidget(QLabel("Approved By:"))
        sig_layout.addWidget(self.approved_by_input)
        self.main_layout.addWidget(sig_group)
        
        # Action Buttons
        btns = QHBoxLayout()
        self.save_btn = QPushButton("Save Request")
        self.save_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 10px; font-weight: bold;")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.save_btn)
        btns.addWidget(self.cancel_btn)
        self.main_layout.addLayout(btns)
        
        if self.pr_id:
            self.load_pr_data()
        else:
            self.add_blank_row()
            self.auto_generate_pr_no()

    def auto_generate_pr_no(self):
        with SessionLocal() as session:
            last_pr = session.query(PurchaseRequest).order_by(PurchaseRequest.id.desc()).first()
            if last_pr and last_pr.pr_no.isdigit():
                next_no = int(last_pr.pr_no) + 1
                self.pr_no_input.setText(str(next_no).zfill(6))
            else:
                self.pr_no_input.setText("000001")

    def add_blank_row(self):
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)
        # Default values
        self.items_table.setItem(row, 3, QTableWidgetItem("0.00")) # Price
        self.items_table.setItem(row, 4, QTableWidgetItem("1"))    # QTY
        self.items_table.setItem(row, 5, QTableWidgetItem("PC"))   # Unit
        self.items_table.setItem(row, 6, QTableWidgetItem("0.00")) # Total
        # Make total non-editable
        self.items_table.item(row, 6).setFlags(Qt.ItemFlag.ItemIsEnabled)

    def remove_selected_row(self):
        curr = self.items_table.currentRow()
        if curr >= 0:
            self.items_table.removeRow(curr)
            self.update_grand_total()

    def calculate_row_total(self, item):
        self.items_table.blockSignals(True)
        row = item.row()
        try:
            price_item = self.items_table.item(row, 3)
            qty_item = self.items_table.item(row, 4)
            if price_item and qty_item:
                price = float(price_item.text().replace(',', ''))
                qty = float(qty_item.text().replace(',', ''))
                total = price * qty
                total_item = self.items_table.item(row, 6)
                if not total_item:
                    total_item = QTableWidgetItem()
                    self.items_table.setItem(row, 6, total_item)
                total_item.setText(f"{total:,.2f}")
        except ValueError:
            pass
        self.items_table.blockSignals(False)
        self.update_grand_total()

    def update_grand_total(self):
        grand_total = 0.0
        for row in range(self.items_table.rowCount()):
            try:
                txt = self.items_table.item(row, 6).text().replace(',', '')
                grand_total += float(txt)
            except (ValueError, AttributeError):
                continue
        self.total_label.setText(f"Estimated Total: Php. {grand_total:,.2f}")

    def load_pr_data(self):
        with SessionLocal() as session:
            pr = session.query(PurchaseRequest).options(joinedload(PurchaseRequest.items)).get(self.pr_id)
            if pr:
                rd = pr.request_date
                self.date_input.setDate(QDate(rd.year, rd.month, rd.day))
                self.pr_no_input.setText(pr.pr_no)
                self.dept_input.setText(pr.department)
                self.end_user_input.setText(pr.end_user or "")
                self.position_input.setText(pr.position or "")
                self.prepared_by_input.setText(pr.prepared_by or "")
                self.approved_by_input.setText(pr.approved_by or "")
                
                self.items_table.setRowCount(0)
                for item in pr.items:
                    row = self.items_table.rowCount()
                    self.items_table.insertRow(row)
                    self.items_table.setItem(row, 0, QTableWidgetItem(item.description))
                    self.items_table.setItem(row, 1, QTableWidgetItem(item.purpose or ""))
                    self.items_table.setItem(row, 2, QTableWidgetItem(item.for_dept or ""))
                    self.items_table.setItem(row, 3, QTableWidgetItem(f"{item.price:.2f}"))
                    self.items_table.setItem(row, 4, QTableWidgetItem(f"{item.qty:.0f}"))
                    self.items_table.setItem(row, 5, QTableWidgetItem(item.unit or ""))
                    self.items_table.setItem(row, 6, QTableWidgetItem(f"{item.total:.2f}"))
                self.update_grand_total()

    def get_data(self):
        items = []
        for r in range(self.items_table.rowCount()):
            try:
                items.append({
                    "description": self.items_table.item(r, 0).text().strip().upper(),
                    "purpose": self.items_table.item(r, 1).text().strip().upper() if self.items_table.item(r, 1) else "",
                    "for_dept": self.items_table.item(r, 2).text().strip().upper() if self.items_table.item(r, 2) else "",
                    "price": float(self.items_table.item(r, 3).text().replace(',', '')),
                    "qty": float(self.items_table.item(r, 4).text().replace(',', '')),
                    "unit": self.items_table.item(r, 5).text().strip().upper() if self.items_table.item(r, 5) else "",
                    "total": float(self.items_table.item(r, 6).text().replace(',', ''))
                })
            except (ValueError, AttributeError):
                continue

        return {
            "pr_no": self.pr_no_input.text().strip(),
            "date": self.date_input.date().toPyDate(),
            "dept": self.dept_input.text().strip().upper(),
            "end_user": self.end_user_input.text().strip().upper(),
            "position": self.position_input.text().strip().upper(),
            "prepared_by": self.prepared_by_input.text().strip().upper(),
            "approved_by": self.approved_by_input.text().strip().upper(),
            "items": items
        }

class PurchaseManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        header = QLabel("Purchase Request Management")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #1F4E78; margin-bottom: 10px;")
        layout.addWidget(header)
        
        btns = QHBoxLayout()
        self.create_btn = QPushButton("+ New Purchase Request")
        self.create_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.create_btn.clicked.connect(self.create_pr)
        
        self.export_btn = QPushButton("📋 Export to Excel (Print)")
        self.export_btn.clicked.connect(self.export_pr)
        
        self.delete_btn = QPushButton("🗑 Delete")
        self.delete_btn.clicked.connect(self.delete_pr)
        
        btns.addWidget(self.create_btn)
        btns.addWidget(self.export_btn)
        btns.addWidget(self.delete_btn)
        btns.addStretch()
        layout.addLayout(btns)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Date", "PR No.", "Department", "End-User", "Total Amt", "ID"])
        self.table.setColumnHidden(5, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self.edit_pr)
        layout.addWidget(self.table)
        
        self.load_data()

    def load_data(self):
        with SessionLocal() as session:
            prs = session.query(PurchaseRequest).options(joinedload(PurchaseRequest.items)).order_by(PurchaseRequest.id.desc()).all()
            self.table.setRowCount(len(prs))
            for i, pr in enumerate(prs):
                total_amt = sum(item.total for item in pr.items)
                self.table.setItem(i, 0, QTableWidgetItem(pr.request_date.strftime("%Y-%m-%d")))
                self.table.setItem(i, 1, QTableWidgetItem(pr.pr_no))
                self.table.setItem(i, 2, QTableWidgetItem(pr.department))
                self.table.setItem(i, 3, QTableWidgetItem(pr.end_user or ""))
                self.table.setItem(i, 4, QTableWidgetItem(f"P{total_amt:,.2f}"))
                self.table.setItem(i, 5, QTableWidgetItem(str(pr.id)))

    def create_pr(self):
        dialog = PurchaseRequestDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            self.save_pr(None, data)

    def edit_pr(self, row, col):
        pr_id = int(self.table.item(row, 5).text())
        dialog = PurchaseRequestDialog(pr_id, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            self.save_pr(pr_id, data)

    def save_pr(self, pr_id, data):
        with SessionLocal() as session:
            try:
                if pr_id:
                    pr = session.query(PurchaseRequest).get(pr_id)
                    # Clear old items
                    for item in pr.items:
                        session.delete(item)
                else:
                    pr = PurchaseRequest()
                    session.add(pr)
                
                pr.pr_no = data["pr_no"]
                d = data["date"]
                pr.request_date = datetime(d.year, d.month, d.day)
                pr.department = data["dept"]
                pr.end_user = data["end_user"]
                pr.position = data["position"]
                pr.prepared_by = data["prepared_by"]
                pr.approved_by = data["approved_by"]
                
                session.flush()
                
                for item_data in data["items"]:
                    p_item = PurchaseItem(
                        pr_id=pr.id,
                        description=item_data["description"],
                        purpose=item_data["purpose"],
                        for_dept=item_data["for_dept"],
                        price=item_data["price"],
                        qty=item_data["qty"],
                        unit=item_data["unit"],
                        total=item_data["total"]
                    )
                    session.add(p_item)
                
                session.commit()
                self.load_data()
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to save PR: {str(e)}")

    def delete_pr(self):
        row = self.table.currentRow()
        if row < 0: return
        pr_id = int(self.table.item(row, 5).text())
        if QMessageBox.question(self, "Confirm", "Delete this Purchase Request?") == QMessageBox.StandardButton.Yes:
            with SessionLocal() as session:
                pr = session.query(PurchaseRequest).get(pr_id)
                session.delete(pr)
                session.commit()
                self.load_data()

    def export_pr(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selection Required", "Please select a Purchase Request to export.")
            return
        
        pr_id = int(self.table.item(row, 5).text())
        from form_generator import generate_purchase_request_excel
        try:
            filename = generate_purchase_request_excel(pr_id)
            QMessageBox.information(self, "Success", f"Purchase Request exported to:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")
