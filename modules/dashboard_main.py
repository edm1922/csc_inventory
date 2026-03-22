import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QFrame, QLineEdit, QPushButton,
                             QDialog, QFormLayout, QMessageBox)
from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush
import os
import webbrowser

from core.database import SessionLocal, Item, Stock, Location
from core.config import evaluate_stock_status

class FilteredReportDialog(QDialog):
    def __init__(self, current_location, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Filtered Report")
        self.setMinimumSize(600, 400)
        
        self.current_location = current_location
        self.layout = QVBoxLayout(self)
        
        # Filter Selection
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Select Stock Category:"))
        
        self.category_cb = QComboBox()
        self.category_cb.addItems(["Low Stock", "Needs Restock", "Healthy Stock", "ALL ALERTS (Low + Restock)"])
        self.category_cb.setStyleSheet("""
            QComboBox { padding: 5px; border: 1px solid #bdc3c7; border-radius: 3px; background: white; color: black; }
        """)
        self.category_cb.currentTextChanged.connect(self.load_preview)
        filter_layout.addWidget(self.category_cb)
        
        filter_layout.addStretch()
        self.layout.addLayout(filter_layout)
        
        # Preview Table
        preview_label = QLabel("Report Preview:")
        preview_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.layout.addWidget(preview_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Item Name", "Quantity", "Unit", "Status", "Location"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("QTableWidget { background: white; color: black; }")
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.print_btn = QPushButton("🖨️ Print / Export PDF (Browser)")
        self.print_btn.setStyleSheet("padding: 8px; background-color: #2980b9; color: white; font-weight: bold; border-radius: 4px;")
        self.print_btn.clicked.connect(self.generate_report)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("padding: 8px;")
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.print_btn)
        self.layout.addLayout(btn_layout)
        
        self.report_data = []
        self.load_preview()
        
    def load_preview(self):
        category = self.category_cb.currentText()
        db = SessionLocal()
        try:
            # Query all stocks if "ALL", or specific location
            # To make it fully comprehensive, we fetch based on the dashboard's current location or ALL.
            # We'll just fetch ALL stocks and filter.
            stocks = db.query(Stock).all()
            
            self.report_data = []
            
            for st in stocks:
                # If we meant to restrict to dashboard location, uncomment the next lines:
                # if self.current_location != "ALL LOCATIONS" and st.location.name != self.current_location:
                #     continue
                
                item = st.item
                qty = st.quantity
                unit = (item.unit or "").strip().upper()
                name = item.name
                loc_name = st.location.name
                
                cat = evaluate_stock_status(unit, qty, item.standard_stock)
                
                # Filter logic
                match = False
                if category == "ALL ALERTS (Low + Restock)":
                    match = cat in ["Low Stock", "Needs Restock"]
                else:
                    match = (cat == category)
                    
                if match:
                    self.report_data.append({
                        "name": name,
                        "qty": qty,
                        "unit": unit,
                        "status": cat,
                        "location": loc_name
                    })
                    
            self.populate_table()
            
        finally:
            db.close()
            
    def populate_table(self):
        self.table.setRowCount(len(self.report_data))
        for row, data in enumerate(self.report_data):
            self.table.setItem(row, 0, QTableWidgetItem(data["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(f"{data['qty']:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(data["unit"]))
            self.table.setItem(row, 3, QTableWidgetItem(data["status"]))
            self.table.setItem(row, 4, QTableWidgetItem(data["location"]))
            
        if not self.report_data:
            self.print_btn.setEnabled(False)
            self.print_btn.setText("No items match filter")
        else:
            self.print_btn.setEnabled(True)
            self.print_btn.setText("🖨️ Print / Export PDF")
            
    def generate_report(self):
        if not self.report_data:
            QMessageBox.information(self, "No Data", "There is no data to generate a report.")
            return
            
        category = self.category_cb.currentText()
        
        html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Inventory Report</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #333; }}
                h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                h3 {{ color: #7f8c8d; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #bdc3c7; padding: 12px; text-align: left; }}
                th {{ background-color: #ecf0f1; color: #2c3e50; font-weight: bold; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .status-Needs {{ color: #e74c3c; font-weight: bold; }}
                .status-Low {{ color: #f39c12; font-weight: bold; }}
                .status-Healthy {{ color: #27ae60; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>📦 Inventory Status Report</h1>
            <h3>Filtered Category: {category}</h3>
            <table>
                <tr>
                    <th>Item Name</th>
                    <th>Quantity</th>
                    <th>Unit</th>
                    <th>Status</th>
                    <th>Location</th>
                </tr>
        """
        
        for d in self.report_data:
            status_class = "status-Healthy"
            if "Needs" in d["status"]: status_class = "status-Needs"
            elif "Low" in d["status"]: status_class = "status-Low"
            
            html += f"""
                <tr>
                    <td>{d["name"]}</td>
                    <td><b>{d["qty"]:.2f}</b></td>
                    <td>{d["unit"]}</td>
                    <td class="{status_class}">{d["status"]}</td>
                    <td>{d["location"]}</td>
                </tr>
            """
            
        html += """
            </table>
            <p style="margin-top: 30px; font-size: 12px; color: #95a5a6;">
                Generated automatically by the Unified Inventory System.
            </p>
        </body>
        </html>
        """
        
        try:
            filepath = os.path.abspath("inventory_report.html")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
            
            webbrowser.open("file://" + filepath)
            QMessageBox.information(self, "Success", "Report opened in your default browser. You can use Ctrl+P to Print or Save as PDF.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate report: {e}")

class PieChart(QFrame):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(200, 200)
        self.data = [] # List of tuples (value, color, label)
        
    def set_data(self, data):
        self.data = data
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        margin = 20
        size = min(rect.width(), rect.height()) - margin * 2
        x = (rect.width() - size) / 2
        y = (rect.height() - size) / 2
        pie_rect = QRectF(x, y, size, size)
        
        total = sum([val for val, color, label in self.data])
        if total == 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#ecf0f1"))
            painter.drawEllipse(pie_rect)
            painter.setPen(Qt.GlobalColor.black)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No Data")
            return
            
        start_angle = 0
        for val, color, label in self.data:
            span_angle = (val / total) * 360 * 16 # 1/16th of a degree
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPie(pie_rect, int(start_angle), int(span_angle))
            start_angle += span_angle
            
        # Draw legend
        leg_x = x + size + 20
        leg_y = y + 20
        painter.setPen(Qt.GlobalColor.black)
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        for val, color, label in self.data:
            painter.setBrush(QColor(color))
            painter.drawRect(int(leg_x), int(leg_y), 12, 12)
            painter.drawText(int(leg_x + 20), int(leg_y + 11), f"{label} ({val})")
            leg_y += 25

class BarChart(QFrame):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(300, 200)
        self.data = [] # List of tuples (value, color, label)
        
    def set_data(self, data):
        self.data = data
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        margin_x = 40
        margin_y = 30
        
        # Draw axes
        painter.setPen(QPen(QColor("#7f8c8d"), 2))
        painter.drawLine(margin_x, margin_y, margin_x, rect.height() - margin_y)
        painter.drawLine(margin_x, rect.height() - margin_y, rect.width() - margin_x, rect.height() - margin_y)
        
        if not self.data:
            return
            
        max_val = max([v for v, c, l in self.data]) if self.data else 0
        if max_val == 0:
            max_val = 1
            
        # Draw ticks on Y axis
        painter.setPen(QColor("#95a5a6"))
        tick_steps = 5
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        for i in range(tick_steps + 1):
            val_tick = (max_val / tick_steps) * i
            y_tick = rect.height() - margin_y - (val_tick / max_val) * (rect.height() - margin_y * 2 - 20)
            painter.drawLine(margin_x - 5, int(y_tick), margin_x, int(y_tick))
            painter.drawText(5, int(y_tick + 5), f"{val_tick:.0f}")
            
        num_bars = len(self.data)
        available_width = rect.width() - margin_x * 2
        bar_width = min(60, available_width / (num_bars * 1.5))
        spacing = (available_width - (num_bars * bar_width)) / (num_bars + 1)
        
        available_height = rect.height() - margin_y * 2 - 20 # 20 for label
        
        x = margin_x + spacing
        for val, color, label in self.data:
            bar_height = (val / max_val) * available_height
            y = rect.height() - margin_y - bar_height
            
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(int(x), int(y), int(bar_width), int(bar_height))
            
            # draw label
            painter.setPen(Qt.GlobalColor.black)
            font.setPointSize(9)
            painter.setFont(font)
            text_width = painter.fontMetrics().horizontalAdvance(str(label))
            label_x = x + (bar_width - text_width) / 2
            painter.drawText(int(label_x), int(rect.height() - margin_y + 18), str(label))
            
            # draw value on top
            val_str = str(val)
            val_width = painter.fontMetrics().horizontalAdvance(val_str)
            val_x = x + (bar_width - val_width) / 2
            painter.drawText(int(val_x), int(y - 5), val_str)
            
            x += bar_width + spacing

class HighlightCard(QFrame):
    def __init__(self, title, value, color):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid #ecf0f1;
                border-top: 5px solid {color};
                border-radius: 5px;
            }}
        """)
        self.setFixedSize(200, 100)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("color: #7f8c8d; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.val_lbl = QLabel(str(value))
        self.val_lbl.setStyleSheet(f"color: {color}; font-size: 32px; font-weight: bold; background: transparent; border: none;")
        self.val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.val_lbl)
        
    def update_value(self, value):
        self.val_lbl.setText(str(value))

class SmartDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.setStyleSheet("background-color: #f5f6fa;")
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Smart Inventory Analysis")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50; background: transparent;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.loc_cb = QComboBox()
        self.loc_cb.addItems(["MAIN OFFICE", "WAREHOUSE"])
        self.loc_cb.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                font-size: 14px;
                background: white;
                color: black;
            }
        """)
        self.loc_cb.currentTextChanged.connect(self.load_data)
        header_layout.addWidget(self.loc_cb)
        
        self.report_btn = QPushButton("📑 Generate Report")
        self.report_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                background-color: #8e44ad;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #9b59b6; }
        """)
        self.report_btn.clicked.connect(self.open_report_dialog)
        header_layout.addWidget(self.report_btn)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                background-color: #3498db;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        refresh_btn.clicked.connect(self.load_data)
        header_layout.addWidget(refresh_btn)
        
        self.main_layout.addLayout(header_layout)
        
        # Cards
        cards_layout = QHBoxLayout()
        self.total_card = HighlightCard("Total Items", 0, "#34495e")
        self.healthy_card = HighlightCard("Healthy Stock", 0, "#2ecc71")
        self.low_card = HighlightCard("Low Stock", 0, "#f1c40f")
        self.restock_card = HighlightCard("Needs Restock", 0, "#e74c3c")
        
        cards_layout.addWidget(self.total_card)
        cards_layout.addWidget(self.healthy_card)
        cards_layout.addWidget(self.low_card)
        cards_layout.addWidget(self.restock_card)
        cards_layout.addStretch()
        self.main_layout.addLayout(cards_layout)
        
        # Charts
        charts_layout = QHBoxLayout()
        
        pie_container = QFrame()
        pie_container.setStyleSheet("background: white; border-radius: 10px;")
        pie_layout = QVBoxLayout(pie_container)
        pie_title = QLabel("Stock Distribution")
        pie_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pie_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 14px;")
        pie_layout.addWidget(pie_title)
        self.pie_chart = PieChart()
        pie_layout.addWidget(self.pie_chart)
        
        bar_container = QFrame()
        bar_container.setStyleSheet("background: white; border-radius: 10px;")
        bar_layout = QVBoxLayout(bar_container)
        bar_title = QLabel("Item Counts per Category")
        bar_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bar_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 14px;")
        bar_layout.addWidget(bar_title)
        self.bar_chart = BarChart()
        bar_layout.addWidget(self.bar_chart)
        
        charts_layout.addWidget(pie_container, 1)
        charts_layout.addWidget(bar_container, 1)
        self.main_layout.addLayout(charts_layout)
        
        # Table
        table_container = QFrame()
        table_container.setStyleSheet("background: white; border-radius: 10px; padding: 10px;")
        t_layout = QVBoxLayout(table_container)
        
        t_header = QHBoxLayout()
        t_title = QLabel("Flagged Items List")
        t_title.setStyleSheet("font-weight: bold; font-size: 16px; color: #2c3e50;")
        
        self.search_le = QLineEdit()
        self.search_le.setPlaceholderText("Search items...")
        self.search_le.setStyleSheet("padding: 5px; border-radius: 5px; border: 1px solid #bdc3c7; background: white; color: black;")
        self.search_le.textChanged.connect(self.filter_table)
        self.search_le.setMaximumWidth(300)
        
        t_header.addWidget(t_title)
        t_header.addStretch()
        t_header.addWidget(self.search_le)
        t_layout.addLayout(t_header)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Item Name", "Unit", "Quantity", "Category"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ecf0f1;
                gridline-color: #bdc3c7;
                background-color: white;
                color: black;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                font-weight: bold;
                padding: 8px;
                border: 1px solid #2c3e50;
                min-height: 35px;
            }
        """)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t_layout.addWidget(self.table)
        
        self.main_layout.addWidget(table_container, 1)
        
        self.flagged_items_data = []
        
        QTimer.singleShot(100, self.load_data)

    def open_report_dialog(self):
        loc = self.loc_cb.currentText()
        d = FilteredReportDialog(loc, self)
        d.exec()

    def load_data(self):
        loc_name = self.loc_cb.currentText()
        db = SessionLocal()
        try:
            loc = db.query(Location).filter(Location.name == loc_name).first()
            if not loc:
                return
                
            stocks = db.query(Stock).filter(Stock.location_id == loc.id).all()
            
            healthy = 0
            low = 0
            restock = 0
            total = len(stocks)
            
            flagged_items = []
            
            for st in stocks:
                item = st.item
                qty = st.quantity
                unit = (item.unit or "").strip().upper()
                name = item.name
                
                cat = evaluate_stock_status(unit, qty, item.standard_stock)
                
                if cat == "Healthy Stock":
                    healthy += 1
                elif cat == "Low Stock":
                    low += 1
                    flagged_items.append((name, unit, qty, cat, "⚠️", "#f1c40f")) # Yellow
                elif cat == "Needs Restock":
                    restock += 1
                    flagged_items.append((name, unit, qty, cat, "❗", "#e74c3c")) # Red
                    
            self.total_card.update_value(total)
            self.healthy_card.update_value(healthy)
            self.low_card.update_value(low)
            self.restock_card.update_value(restock)
            
            chart_data = []
            if healthy > 0: chart_data.append((healthy, "#2ecc71", "Healthy"))
            if low > 0: chart_data.append((low, "#f1c40f", "Low"))
            if restock > 0: chart_data.append((restock, "#e74c3c", "Restock"))
            
            self.pie_chart.set_data(chart_data)
            self.bar_chart.set_data(chart_data)
            
            self.flagged_items_data = flagged_items
            self.populate_table(self.flagged_items_data)
            
        finally:
            db.close()
            
    def populate_table(self, data):
        self.table.setRowCount(len(data))
        for row, (name, unit, qty, cat, icon, color) in enumerate(data):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(unit))
            self.table.setItem(row, 2, QTableWidgetItem(f"{qty:.2f}"))
            
            cat_item = QTableWidgetItem(f"{icon} {cat}")
            cat_item.setForeground(QColor(color))
            # Make font bold
            font = cat_item.font()
            font.setBold(True)
            cat_item.setFont(font)
            
            self.table.setItem(row, 3, cat_item)
            
    def filter_table(self, text):
        if not self.flagged_items_data: return
        filtered = []
        q = text.lower()
        for row_data in self.flagged_items_data:
            name = row_data[0].lower()
            if q in name:
                filtered.append(row_data)
        self.populate_table(filtered)
