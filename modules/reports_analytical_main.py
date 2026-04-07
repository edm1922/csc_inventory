import sys
import os
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QFrame, QLineEdit, QPushButton,
                             QTabWidget, QScrollArea, QListWidget, QListWidgetItem, QProgressBar,
                             QMessageBox, QDialog, QRadioButton, QButtonGroup,
                             QDialogButtonBox)
from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush

from core.database import SessionLocal, Item, Stock, Location, Employee, SupplyRequest, RequestItem, QuickPullLog, QuickPullItem, PurchaseRequest, PurchaseItem, Department, InventoryActionLog
from core.config import evaluate_stock_status, get_effective_threshold, get_thresholds
from core.html_generator import generate_html_report
from core.excel_generator import generate_excel_report
from dashboard_main import FilteredReportDialog
from sqlalchemy.orm import joinedload
from sqlalchemy import func

# Reuse Chart components from dashboard_main (or redefine here if needed)
# For independence, I will redefine the base chart classes here with enhancements.

class PieChart(QFrame):
    slice_clicked = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(250, 250)
        self.data = [] # List of tuples (value, color, label)
        
    def set_data(self, data):
        self.data = data
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        margin = 30
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
        painter.setPen(QColor("#2F3542"))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        
        # Limit to top 5 + Others if many
        display_data = self.data[:5]
        if len(self.data) > 5:
            others_val = sum([v for v, c, l in self.data[5:]])
            display_data.append((others_val, "#7f8c8d", "Others"))

        for val, color, label in display_data:
            painter.setBrush(QColor(color))
            painter.drawRect(int(leg_x), int(leg_y), 10, 10)
            painter.drawText(int(leg_x + 18), int(leg_y + 9), f"{label}")
            leg_y += 22

    def mousePressEvent(self, event):
        total = sum([val for val, color, label in self.data])
        if total == 0: return
        
        rect = self.rect()
        margin = 30
        size = min(rect.width(), rect.height()) - margin * 2
        center = rect.center()
        
        dx = event.position().x() - center.x()
        dy = event.position().y() - center.y()
        dist = (dx**2 + dy**2)**0.5
        
        if dist > size/2: return
        
        import math
        # atan2(y, x) -> y is -dy because screen y grows downwards
        angle = math.degrees(math.atan2(-dy, dx)) 
        if angle < 0: angle += 360
        
        # QPainter.drawPie: 0 is 3 o'clock, positive is counter-clockwise.
        # atan2: 0 is 3 o'clock, positive is counter-clockwise. Perfect.
        
        start_angle = 0
        for val, color, label in self.data:
            span_angle = (val / total) * 360
            if start_angle <= angle <= start_angle + span_angle:
                self.slice_clicked.emit(label)
                break
            start_angle += span_angle


class BarChart(QFrame):
    bar_clicked = pyqtSignal(str)
    
    def __init__(self, title=""):
        super().__init__()
        self.setMinimumSize(300, 250)
        self.data = [] 
        self.title = title
        
    def set_data(self, data):
        self.data = data
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        margin_x = 50
        margin_y = 40
        
        # Draw axes
        painter.setPen(QPen(QColor("#7f8c8d"), 2))
        painter.drawLine(margin_x, margin_y, margin_x, rect.height() - margin_y)
        painter.drawLine(margin_x, rect.height() - margin_y, rect.width() - margin_x, rect.height() - margin_y)
        
        if not self.data:
            return
            
        max_val = max([v for v, c, l in self.data]) if self.data else 0
        if max_val == 0: max_val = 1
            
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
        
        available_height = rect.height() - margin_y * 2 - 20 
        
        x = margin_x + spacing
        bar_color = QColor("#4A90E2") # Subdued Blue as primary
        
        for i, (val, color, label) in enumerate(self.data):
            bar_height = (val / max_val) * available_height
            y = rect.height() - margin_y - bar_height
            
            # Use 1-2 colors only as requested
            current_color = bar_color if i % 2 == 0 else QColor("#A4C8F0")
            painter.setBrush(current_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(int(x), int(y), int(bar_width), int(bar_height))
            
            # draw label
            painter.setPen(QColor("#7f8c8d"))
            font.setPointSize(8)
            painter.setFont(font)
            
            display_label = str(label)
            if len(display_label) > 12: display_label = display_label[:10] + ".."
            
            text_width = painter.fontMetrics().horizontalAdvance(display_label)
            label_x = x + (bar_width - text_width) / 2
            painter.drawText(int(label_x), int(rect.height() - margin_y + 18), display_label)
            
            # draw value on top
            painter.setPen(QColor("#2F3542"))
            val_str = f"{val:.0f}"
            val_width = painter.fontMetrics().horizontalAdvance(val_str)
            val_x = x + (bar_width - val_width) / 2
            painter.drawText(int(val_x), int(y - 5), val_str)
            
            x += bar_width + spacing

    def mousePressEvent(self, event):
        if not self.data: return
        
        rect = self.rect()
        margin_x = 50
        margin_y = 40
        available_width = rect.width() - margin_x * 2
        num_bars = len(self.data)
        bar_width = min(60, available_width / (num_bars * 1.5))
        spacing = (available_width - (num_bars * bar_width)) / (num_bars + 1)
        
        click_x = event.position().x()
        x = margin_x + spacing
        
        for i, (val, color, label) in enumerate(self.data):
            if x <= click_x <= x + bar_width:
                self.bar_clicked.emit(label)
                break
            x += bar_width + spacing


class LineChart(QFrame):
    def __init__(self, title=""):
        super().__init__()
        self.setMinimumSize(400, 250)
        self.data = [] # List of (x_label, value)
        self.title = title
        
    def set_data(self, data):
        self.data = data
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        margin_x = 60
        margin_y = 40
        
        # Draw axes
        painter.setPen(QPen(QColor("#7f8c8d"), 2))
        painter.drawLine(margin_x, margin_y, margin_x, rect.height() - margin_y)
        painter.drawLine(margin_x, rect.height() - margin_y, rect.width() - margin_x, rect.height() - margin_y)
        
        if not self.data:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No Trend Data")
            return
            
        values = [v for l, v in self.data]
        max_val = max(values) if values else 0
        if max_val == 0: max_val = 1
        
        # Draw Y Ticks
        painter.setPen(QColor("#95a5a6"))
        tick_steps = 5
        for i in range(tick_steps + 1):
            val_tick = (max_val / tick_steps) * i
            y_tick = rect.height() - margin_y - (val_tick / max_val) * (rect.height() - margin_y * 2 - 20)
            painter.drawLine(margin_x - 5, int(y_tick), margin_x, int(y_tick))
            painter.drawText(5, int(y_tick + 5), f"{val_tick:.0f}")
            
        # Draw Data Line
        pen = QPen(QColor("#3498db"), 3)
        painter.setPen(pen)
        
        points = []
        num_points = len(self.data)
        spacing = (rect.width() - margin_x * 2) / (num_points - 1) if num_points > 1 else 0
        
        for i, (label, val) in enumerate(self.data):
            px = margin_x + i * spacing
            py = rect.height() - margin_y - (val / max_val) * (rect.height() - margin_y * 2 - 20)
            points.append((px, py))
            
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i+1]
            painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))
            
        # Draw Data Points
        painter.setBrush(QColor("#2980b9"))
        painter.setPen(Qt.PenStyle.NoPen)
        for px, py in points:
            painter.drawEllipse(int(px - 4), int(py - 4), 8, 8)
            
        # Draw X Labels (every few points to avoid overlap)
        painter.setPen(Qt.GlobalColor.black)
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        step = max(1, num_points // 6)
        for i, (label, val) in enumerate(self.data):
            if i % step == 0:
                px = margin_x + i * spacing
                text_width = painter.fontMetrics().horizontalAdvance(str(label))
                painter.drawText(int(px - text_width/2), int(rect.height() - margin_y + 18), str(label))

class HighlightCard(QFrame):
    def __init__(self, title, value, color):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: none;
                border-top: 3px solid {color};
                border-radius: 4px;
            }}
        """)
        self.setFixedSize(200, 80)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(2)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("color: #7f8c8d; font-size: 11px; text-transform: uppercase; background: transparent;")
        
        self.val_lbl = QLabel(str(value))
        self.val_lbl.setStyleSheet(f"color: #2F3542; font-size: 20px; font-weight: bold; background: transparent;")
        
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.val_lbl)
        
    def update_value(self, value):
        self.val_lbl.setText(str(value))

class InventoryAnalysisView(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #F5F6FA;")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(25, 20, 25, 20)
        self.main_layout.setSpacing(20)
        
        # Header / Filters
        filter_layout = QHBoxLayout()
        self.loc_cb = QComboBox()
        
        with SessionLocal() as db:
            locations = [loc.name for loc in db.query(Location).order_by(Location.name).all()]
        self.loc_cb.addItems(locations + ["ALL LOCATIONS"])
        
        self.loc_cb.setStyleSheet("padding: 8px; border-radius: 5px; min-width: 150px; background: white; color: black;")
        self.loc_cb.currentTextChanged.connect(self.load_data)
        filter_layout.addWidget(QLabel("<b>Location Filter:</b>"))
        filter_layout.addWidget(self.loc_cb)
        
        self.refresh_btn = QPushButton("🔄 Refresh Analytics")
        self.refresh_btn.setStyleSheet("padding: 8px 15px; background-color: #3498db; color: white; font-weight: bold; border-radius: 5px;")
        self.refresh_btn.clicked.connect(self.load_data)
        
        filter_layout.addStretch()
        filter_layout.addWidget(self.refresh_btn)
        self.main_layout.addLayout(filter_layout)
        
        # Cards
        cards_layout = QHBoxLayout()
        self.total_card = HighlightCard("Total Items", 0, "#34495e")
        self.healthy_card = HighlightCard("Stock Sufficient", 0, "#2ecc71")
        self.restock_card = HighlightCard("Need Restock", 0, "#e74c3c")
        
        cards_layout.addWidget(self.total_card)
        cards_layout.addWidget(self.healthy_card)
        cards_layout.addWidget(self.restock_card)
        self.main_layout.addLayout(cards_layout)
        
        # Charts Area (Top Row)
        top_charts_layout = QHBoxLayout()
        
        # Stock Distribution (Pie) - TOP LEFT
        pie_container = QFrame()
        pie_container.setStyleSheet("background: white; border-radius: 8px; border: none;")
        pie_layout = QVBoxLayout(pie_container)
        pie_layout.setContentsMargins(20, 15, 20, 15)
        pie_title = QLabel("Stock Category Distribution")
        pie_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pie_title.setStyleSheet("font-weight: bold; color: #2c3e50; padding: 10px;")
        pie_layout.addWidget(pie_title)
        self.pie_chart = PieChart()
        pie_layout.addWidget(self.pie_chart)
        top_charts_layout.addWidget(pie_container, 1)
        
        # Monthly Issuance Trends (Line) - TOP RIGHT
        trends_container = QFrame()
        trends_container.setStyleSheet("background: white; border-radius: 8px; border: none;")
        trends_vbox = QVBoxLayout(trends_container)
        trends_vbox.setContentsMargins(20, 15, 20, 15)
        trends_title = QLabel("📉 Monthly Issuance Trends")
        trends_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        trends_title.setStyleSheet("font-weight: bold; color: #2c3e50; padding: 10px;")
        trends_vbox.addWidget(trends_title)
        self.trend_chart = LineChart()
        trends_vbox.addWidget(self.trend_chart)
        top_charts_layout.addWidget(trends_container, 1)
        
        self.main_layout.addLayout(top_charts_layout)
        
        # Bottom Area
        bottom_layout = QHBoxLayout()
        
        # Item Activity Log (New) - BOTTOM LEFT
        activity_container = QFrame()
        activity_container.setStyleSheet("background: white; border-radius: 8px; border: none;")
        activity_vbox = QVBoxLayout(activity_container)
        activity_vbox.setContentsMargins(20, 15, 20, 15)
        activity_title = QLabel("📜 Item Activity Log")
        activity_title.setStyleSheet("font-weight: bold; color: #2c3e50; padding-bottom: 10px;")
        activity_vbox.addWidget(activity_title)
        
        self.activity_list = QListWidget()
        self.activity_list.setStyleSheet("""
            QListWidget { border: none; background: #F8F9FA; border-radius: 5px; font-size: 11px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #eee; }
        """)
        activity_vbox.addWidget(self.activity_list)
        bottom_layout.addWidget(activity_container, 1)
        
        # Recurring Stock Issues (Table) - BOTTOM RIGHT
        recurring_container = QFrame()
        recurring_container.setStyleSheet("background: white; border-radius: 8px; border: none;")
        recurring_vbox = QVBoxLayout(recurring_container)
        recurring_vbox.setContentsMargins(20, 15, 20, 15)
        recurring_title = QLabel("⚠️ Recurring Stock Issues")
        recurring_title.setStyleSheet("font-weight: bold; color: #c0392b; padding-bottom: 10px;")
        recurring_vbox.addWidget(recurring_title)
        
        # Table of flagged items moved here
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Item Name", "Description", "Current Qty", "Threshold", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("""
            QTableWidget { background: white; color: black; border: 1px solid #eee; border-radius: 5px; font-size: 11px; }
            QHeaderView::section { background: #fdfdfd; padding: 4px; font-weight: bold; color: #7f8c8d; }
        """)
        recurring_vbox.addWidget(self.table)
        bottom_layout.addWidget(recurring_container, 2) # Wider for the table
        
        self.main_layout.addLayout(bottom_layout)
        
        QTimer.singleShot(500, self.load_data)

    def load_data(self):
        loc_name = self.loc_cb.currentText()
        with SessionLocal() as db:
            query = db.query(Stock).options(joinedload(Stock.item))
            if loc_name != "ALL LOCATIONS":
                query = query.join(Location).filter(Location.name == loc_name)
            
            stocks = query.all()
            
            # Aggregation logic
            healthy = 0
            restock = 0
            total = len(stocks)
            
            critical_items = [] # (qty, color, name)
            
            self.table.setRowCount(0)
            
            for st in stocks:
                item = st.item
                qty = st.quantity
                unit = (item.unit or "").strip().upper()
                threshold, _ = get_effective_threshold(unit, item.standard_stock)
                
                status = evaluate_stock_status(unit, qty, item.standard_stock)
                
                if status == "Stock Sufficient":
                    healthy += 1
                elif status == "Need Restock":
                    restock += 1
                    self.add_table_row(item.name, item.description or "", qty, threshold, status, "#e74c3c")
            
            self.total_card.update_value(total)
            self.healthy_card.update_value(healthy)
            self.restock_card.update_value(restock)
            
            # Charts
            dist_data = []
            if healthy > 0: dist_data.append((healthy, "#2ecc71", "Sufficient"))
            if restock > 0: dist_data.append((restock, "#e74c3c", "Restock"))
            self.pie_chart.set_data(dist_data)
            
            # Load Trends
            self.load_trends(db)
            
            # Load Activity Log (Latest 15)
            self.activity_list.clear()
            logs = db.query(InventoryActionLog).order_by(InventoryActionLog.timestamp.desc()).limit(15).all()
            for log in logs:
                time_str = log.timestamp.strftime("%Y-%m-%d %I:%M %p")
                icon = "✅" if log.action_type == "ADDED" else "✏️" if log.action_type == "UPDATED" else "❌"
                list_item = QListWidgetItem(f"[{time_str}] {log.item_name} \n{icon} {log.action_type}: {log.details}")
                if log.action_type == "REMOVED": list_item.setForeground(QColor("#c0392b"))
                elif log.action_type == "ADDED": list_item.setForeground(QColor("#27ae60"))
                self.activity_list.addItem(list_item)

    def load_trends(self, db):
        # Last 6 months trend
        trends = []
        for i in range(5, -1, -1):
            date = datetime.now() - timedelta(days=i*30)
            month_str = date.strftime("%b")
            start_of_month = datetime(date.year, date.month, 1)
            if date.month == 12:
                end_of_month = datetime(date.year + 1, 1, 1)
            else:
                end_of_month = datetime(date.year, date.month + 1, 1)
                
            count = db.query(func.sum(RequestItem.quantity)) \
                .select_from(RequestItem) \
                .join(SupplyRequest, RequestItem.request_id == SupplyRequest.id) \
                .filter(SupplyRequest.request_date >= start_of_month, 
                        SupplyRequest.request_date < end_of_month).scalar() or 0
            trends.append((month_str, count))
        self.trend_chart.set_data(trends)

    def add_table_row(self, name, description, qty, threshold, status, color):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(description))
        self.table.setItem(row, 2, QTableWidgetItem(f"{qty:.2f}"))
        self.table.setItem(row, 3, QTableWidgetItem(f"{threshold:.2f}"))
        status_item = QTableWidgetItem(status)
        status_item.setForeground(QColor(color))
        font = status_item.font()
        font.setBold(True)
        status_item.setFont(font)
        self.table.setItem(row, 4, status_item)

    def export_inventory_excel(self):
        loc_name = self.loc_cb.currentText()
        with SessionLocal() as db:
            query = db.query(Stock).options(joinedload(Stock.item))
            if loc_name != "ALL LOCATIONS":
                query = query.join(Location).filter(Location.name == loc_name)
            stocks = query.all()

            if not stocks:
                QMessageBox.warning(self, "No Data", "No inventory data found to export.")
                return

            headers = ["Item Name", "Location", "Quantity", "Unit", "Threshold", "Status"]
            data = []
            for st in stocks:
                item = st.item
                unit = (item.unit or "").strip().upper()
                threshold, _ = get_effective_threshold(unit, item.standard_stock)
                status = evaluate_stock_status(unit, st.quantity, item.standard_stock)
                data.append([item.name, st.location.name, st.quantity, unit, threshold, status])

            try:
                filename = f"inventory_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                filepath = generate_excel_report("Inventory Analysis Report", headers, data, filename)
                os.startfile(filepath)
                QMessageBox.information(self, "Success", f"Report exported to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {e}")

class EmployeeAnalysisView(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #F5F6FA;")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(25, 20, 25, 20)
        self.main_layout.setSpacing(20)
        
        # Row 1: Key Metrics (Simplified Cards)
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(15)
        self.top_emp_card = HighlightCard("Top Requester", "---", "#4A90E2")
        self.top_item_card = HighlightCard("Hot Item", "---", "#F39C12")
        self.active_dept_card = HighlightCard("Busy Area", "---", "#2ECC71")
        self.total_req_card = HighlightCard("Total Requests", "0", "#9B59B6")
        
        cards_layout.addWidget(self.top_emp_card)
        cards_layout.addWidget(self.top_item_card)
        cards_layout.addWidget(self.active_dept_card)
        cards_layout.addWidget(self.total_req_card)
        cards_layout.addStretch()
        self.main_layout.addLayout(cards_layout)
        
        # Smart Filters Bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)
        
        filter_bar.addWidget(QLabel("Date Range:"))
        self.date_filter = QComboBox()
        self.date_filter.addItems(["Last 30 Days", "Last 90 Days", "This Year", "All Time"])
        self.date_filter.currentIndexChanged.connect(self.load_aggregate_data)
        filter_bar.addWidget(self.date_filter)
        
        filter_bar.addWidget(QLabel("Department:"))
        self.dept_filter = QComboBox()
        self.dept_filter.addItem("All Departments")
        self.dept_filter.currentIndexChanged.connect(self.load_aggregate_data)
        filter_bar.addWidget(self.dept_filter)
        
        filter_bar.addStretch()
        self.main_layout.addLayout(filter_bar)
        
        # Row 2: Main Content (Charts - 2 Columns)
        charts_row = QHBoxLayout()
        charts_row.setSpacing(20)
        
        # Left: Most Requested Items (BIG BAR CHART)
        bar_container = QFrame()
        bar_container.setStyleSheet("background: white; border-radius: 8px; border: none;")
        bar_layout = QVBoxLayout(bar_container)
        bar_layout.setContentsMargins(20, 15, 20, 15)
        bar_title = QLabel("Most Requested Items")
        bar_title.setStyleSheet("font-weight: bold; color: #2F3542; font-size: 14px;")
        bar_layout.addWidget(bar_title)
        self.top_items_chart = BarChart()
        bar_layout.addWidget(self.top_items_chart)
        charts_row.addWidget(bar_container, 2) # Bigger
        
        # Right: Usage by Role (PIE CHART)
        pie_container = QFrame()
        pie_container.setStyleSheet("background: white; border-radius: 8px; border: none;")
        pie_layout = QVBoxLayout(pie_container)
        pie_layout.setContentsMargins(20, 15, 20, 15)
        pie_title = QLabel("Usage by Role")
        pie_title.setStyleSheet("font-weight: bold; color: #2F3542; font-size: 14px;")
        pie_layout.addWidget(pie_title)
        self.role_usage_chart = PieChart()
        pie_layout.addWidget(self.role_usage_chart)
        charts_row.addWidget(pie_container, 1) # Smaller
        
        self.main_layout.addLayout(charts_row)
        
        # Row 3: Interaction Area (Cleaner Split)
        interaction_row = QHBoxLayout()
        interaction_row.setSpacing(20)
        
        # LEFT: Employee List
        list_container = QFrame()
        list_container.setStyleSheet("background: white; border-radius: 8px; border: none;")
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(15, 15, 15, 15)
        
        list_title = QLabel("Select Employee")
        list_title.setStyleSheet("font-weight: bold; color: #2F3542; font-size: 13px;")
        list_layout.addWidget(list_title)
        
        self.search_le = QLineEdit()
        self.search_le.setPlaceholderText("Search employee...")
        self.search_le.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                border: 1px solid #E1E4E8;
                border-radius: 15px;
                background: #F8F9FA;
                font-size: 12px;
            }
        """)
        self.search_le.textChanged.connect(self.filter_list)
        list_layout.addWidget(self.search_le)
        
        self.emp_list = QListWidget()
        self.emp_list.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
                font-size: 12px;
                color: #2F3542;
            }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #F1F2F6; }
            QListWidget::item:selected { background: #E1F5FE; color: #039BE5; border-radius: 4px; }
        """)
        self.emp_list.itemClicked.connect(self.load_employee_details)
        list_layout.addWidget(self.emp_list)
        interaction_row.addWidget(list_container, 1)
        
        # RIGHT: Request History Table
        table_container = QFrame()
        table_container.setStyleSheet("background: white; border-radius: 8px; border: none;")
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(15, 15, 15, 15)
        
        self.details_lbl = QLabel("Request History Details")
        self.details_lbl.setStyleSheet("font-weight: bold; color: #2F3542; font-size: 13px;")
        table_layout.addWidget(self.details_lbl)
        
        self.details_table = QTableWidget()
        self.details_table.setColumnCount(5)
        self.details_table.setHorizontalHeaderLabels(["Date", "Item Name", "Description", "Qty", "Area"])
        self.details_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.details_table.verticalHeader().setVisible(False)
        self.details_table.setAlternatingRowColors(True)
        self.details_table.setStyleSheet("""
            QTableWidget {
                border: none;
                gridline-color: transparent;
                background: white;
                alternate-background-color: #F8F9FA;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: white;
                color: #7f8c8d;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid #F1F2F6;
                padding: 8px;
            }
        """)
        table_layout.addWidget(self.details_table)
        
        interaction_row.addWidget(table_container, 2)
        
        self.main_layout.addLayout(interaction_row)
        
        # Connect Chart Interactions
        self.top_items_chart.bar_clicked.connect(self.handle_bar_click)
        self.role_usage_chart.slice_clicked.connect(self.handle_slice_click)
        
        QTimer.singleShot(500, self.load_aggregate_data)
        QTimer.singleShot(500, self.load_depts)

    def export_employee_excel(self):
        date_filter_text = self.date_filter.currentText()
        dept_filter_text = self.dept_filter.currentText()
        
        now = datetime.now()
        start_date = None
        if date_filter_text == "Last 30 Days":
            start_date = now - timedelta(days=30)
        elif date_filter_text == "Last 90 Days":
            start_date = now - timedelta(days=90)
        elif date_filter_text == "This Year":
            start_date = datetime(now.year, 1, 1)

        with SessionLocal() as db:
            base_req_query = db.query(SupplyRequest.id)
            if start_date:
                base_req_query = base_req_query.filter(SupplyRequest.request_date >= start_date)
            if dept_filter_text != "All Departments":
                base_req_query = base_req_query.join(Department).filter(Department.area_name == dept_filter_text)
            
            req_ids = [r[0] for r in base_req_query.all()]
            
            if not req_ids:
                QMessageBox.warning(self, "No Data", "No requests found for the selected filters.")
                return

            # Fetch detailed data for excel
            details_query = db.query(Employee.name.label("Employee"), 
                                     Item.name.label("Item"), 
                                     RequestItem.quantity.label("Quantity"), 
                                     SupplyRequest.request_date.label("Date"),
                                     Department.area_name.label("Department")) \
                .select_from(RequestItem) \
                .join(SupplyRequest, RequestItem.request_id == SupplyRequest.id) \
                .join(Employee, SupplyRequest.employee_id == Employee.id) \
                .join(Item, RequestItem.item_id == Item.id) \
                .join(Department, SupplyRequest.department_id == Department.id) \
                .filter(SupplyRequest.id.in_(req_ids)) \
                .order_by(SupplyRequest.request_date.desc())
            
            results = details_query.all()
            headers = ["Employee", "Item", "Quantity", "Date", "Department"]
            data = [[r.Employee, r.Item, r.Quantity, r.Date.strftime("%Y-%m-%d"), r.Department] for r in results]

            try:
                filename = f"employee_usage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                filepath = generate_excel_report("Employee Usage Analytics", headers, data, filename)
                os.startfile(filepath)
                QMessageBox.information(self, "Success", f"Report exported to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {e}")

    def load_depts(self):
        with SessionLocal() as db:
            depts = db.query(Department.area_name).distinct().all()
            self.dept_filter.blockSignals(True)
            self.dept_filter.clear()
            self.dept_filter.addItem("All Departments")
            for (d,) in depts:
                if d: self.dept_filter.addItem(d)
            self.dept_filter.blockSignals(False)

    def handle_bar_click(self, item_name):
        """Filters employees who have requested the clicked item."""
        with SessionLocal() as db:
            emps = db.query(Employee.name).distinct() \
                .join(SupplyRequest).join(RequestItem).join(Item) \
                .filter(Item.name == item_name).all()
            
            valid_names = [e[0] for e in emps]
            
            for i in range(self.emp_list.count()):
                item = self.emp_list.item(i)
                item.setHidden(item.text() not in valid_names)
            
            self.details_lbl.setText(f"<b>Employees who requested: {item_name}</b>")
            # Clear search bar to indicate we're in a special filter mode
            self.search_le.blockSignals(True)
            self.search_le.setText(f"Filtered by: {item_name}")
            self.search_le.blockSignals(False)

    def handle_slice_click(self, label):
        """Filters by Department/Area when a pie slice is clicked."""
        if label == "Others": return
        self.dept_filter.setCurrentText(label)
        self.load_aggregate_data()
        
        QTimer.singleShot(500, self.load_aggregate_data)

    def load_aggregate_data(self):
        date_filter_text = self.date_filter.currentText()
        dept_filter_text = self.dept_filter.currentText()
        
        now = datetime.now()
        start_date = None
        if date_filter_text == "Last 30 Days":
            start_date = now - timedelta(days=30)
        elif date_filter_text == "Last 90 Days":
            start_date = now - timedelta(days=90)
        elif date_filter_text == "This Year":
            start_date = datetime(now.year, 1, 1)

        with SessionLocal() as db:
            # Base Query for SupplyRequests in range
            base_req_query = db.query(SupplyRequest.id)
            if start_date:
                base_req_query = base_req_query.filter(SupplyRequest.request_date >= start_date)
            if dept_filter_text != "All Departments":
                base_req_query = base_req_query.join(Department).filter(Department.area_name == dept_filter_text)
            
            req_ids = [r[0] for r in base_req_query.all()]
            
            # Top 10 Requested Items
            item_query = db.query(Item.name, func.sum(RequestItem.quantity).label('total')) \
                .select_from(Item).join(RequestItem, Item.id == RequestItem.item_id)
            if req_ids:
                item_query = item_query.filter(RequestItem.request_id.in_(req_ids))
            elif start_date or dept_filter_text != "All Departments":
                # If filtered but no requests found
                self.top_items_chart.set_data([])
                self.role_usage_chart.set_data([])
                return

            top_items = item_query.group_by(Item.name).order_by(func.sum(RequestItem.quantity).desc()).limit(10).all()
            
            chart_items = []
            colors = ["#4A90E2", "#357ABD", "#63A1E8", "#82B6EF", "#A4C8F0"]
            for i, (name, total) in enumerate(top_items):
                chart_items.append((total, colors[i % len(colors)], name))
            self.top_items_chart.set_data(chart_items)
            
            # Usage by Department/Area
            role_query = db.query(Department.area_name, func.count(SupplyRequest.id)) \
                .select_from(Department).join(SupplyRequest, Department.id == SupplyRequest.department_id)
            if start_date:
                role_query = role_query.filter(SupplyRequest.request_date >= start_date)
            
            role_usage = role_query.group_by(Department.area_name).all()
            
            role_data = []
            accent_colors = ["#4A90E2", "#2ECC71", "#F39C12", "#9B59B6", "#E74C3C"]
            for name, count in role_usage:
                if not name: name = "Unknown"
                role_data.append((count, accent_colors[len(role_data) % len(accent_colors)], name))
            self.role_usage_chart.set_data(role_data)
            
            # Populate Summary Cards
            # 1. Top Requester
            emp_query = db.query(Employee.name, func.count(SupplyRequest.id)) \
                .select_from(Employee).join(SupplyRequest, Employee.id == SupplyRequest.employee_id)
            if req_ids:
                emp_query = emp_query.filter(SupplyRequest.id.in_(req_ids))
            
            top_emp = emp_query.group_by(Employee.name).order_by(func.count(SupplyRequest.id).desc()).first()
            if top_emp: 
                display_name = top_emp[0].split(" ")[0]
                self.top_emp_card.update_value(display_name)
            else:
                self.top_emp_card.update_value("---")
            
            # 2. Hot Item
            if top_items: self.top_item_card.update_value(top_items[0][0][:12])
            else: self.top_item_card.update_value("---")
            
            # 3. Busy Area
            if role_usage: 
                sorted_roles = sorted(role_usage, key=lambda x: x[1], reverse=True)
                self.active_dept_card.update_value(sorted_roles[0][0] or "N/A")
            else:
                self.active_dept_card.update_value("---")
            
            # 4. Total Requests
            self.total_req_card.update_value(len(req_ids))

            # Load Employee List (Filtered by Dept if selected)
            emp_list_query = db.query(Employee.name).distinct().order_by(Employee.name)
            if dept_filter_text != "All Departments":
                emp_list_query = emp_list_query.join(SupplyRequest).join(Department).filter(Department.area_name == dept_filter_text)
            
            employees = emp_list_query.all()
            self.emp_list.clear()
            for (name,) in employees:
                self.emp_list.addItem(name)

    def filter_list(self, text):
        for i in range(self.emp_list.count()):
            item = self.emp_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def load_employee_details(self, item):
        emp_name = item.text()
        self.details_lbl.setText(f"<b>Request History for: {emp_name}</b>")
        with SessionLocal() as db:
            history = db.query(SupplyRequest).join(Employee).filter(Employee.name == emp_name) \
                .options(joinedload(SupplyRequest.requested_items).joinedload(RequestItem.item),
                         joinedload(SupplyRequest.department)).order_by(SupplyRequest.request_date.desc()).all()
            
            self.details_table.setRowCount(0)
            for req in history:
                date_str = req.request_date.strftime("%Y-%m-%d")
                area = req.department.area_name if req.department else "N/A"
                for ri in req.requested_items:
                    row = self.details_table.rowCount()
                    self.details_table.insertRow(row)
                    self.details_table.setItem(row, 0, QTableWidgetItem(date_str))
                    self.details_table.setItem(row, 1, QTableWidgetItem(ri.item.name))
                    self.details_table.setItem(row, 2, QTableWidgetItem(ri.item.description or ""))
                    self.details_table.setItem(row, 3, QTableWidgetItem(f"{ri.quantity:.2f}"))
                    self.details_table.setItem(row, 4, QTableWidgetItem(area))

    def run_employee_export(self):
        items = self.emp_list.selectedItems()
        if not items:
            QMessageBox.warning(self, "Selection Required", "Please select an employee first.")
            return
            
        emp_name = items[0].text()
        from form_generator import generate_populated_report
        
        with SessionLocal() as session:
            emp = session.query(Employee).filter_by(name=emp_name).first()
            if not emp: return
            
            requests = session.query(RequestItem).join(SupplyRequest).filter(
                SupplyRequest.employee_id == emp.id
            ).options(
                joinedload(RequestItem.item),
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.employee),
                joinedload(RequestItem.supply_request).joinedload(SupplyRequest.department)
            ).order_by(RequestItem.id.desc()).all()

            if not requests:
                QMessageBox.warning(self, "No Data", "No history found for this employee.")
                return

            latest = requests[0]
            role = latest.supply_request.department.role or ""
            area = latest.supply_request.department.area_name or "Unknown"
            shift = latest.supply_request.department.shift or ""
            supervisor = latest.supply_request.department.supervisor or ""

            data_rows = []
            for r in requests:
                data_rows.append((
                    r.supply_request.request_date.strftime("%Y-%m-%d"),
                    r.item.name,
                    r.quantity,
                    r.frequency or ""
                ))

            metadata = {
                "Employee Name": emp_name,
                "Role": role,
                "Area": area,
                "Shift": shift,
                "Supervisor": supervisor
            }
            
            headers = ["Date", "Item Name", "Quantity", "Remarks/Frequency"]
            fname = f"HISTORY_{emp_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            
            try:
                filename = generate_html_report(f"👤 Individual Supply History: {emp_name}", headers, data_rows, fname, metadata=metadata)
                os.startfile(filename)
                QMessageBox.information(self, "Success", f"Report generated and opened: {os.path.basename(filename)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to generate report: {e}")

class ActivityLogView(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #F5F6FA;")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(25, 20, 25, 20)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: white; border-radius: 8px; }
            QTabBar::tab { 
                padding: 10px 20px; 
                background: transparent; 
                border: none;
                border-bottom: 2px solid transparent;
                font-weight: bold;
                color: #7f8c8d;
            }
            QTabBar::tab:selected { 
                color: #4A90E2; 
                border-bottom: 2px solid #4A90E2; 
            }
        """)
        
        # Quick Pull Tab
        self.qp_tab = QWidget()
        qp_layout = QVBoxLayout(self.qp_tab)
        self.qp_table = QTableWidget()
        self.qp_table.setColumnCount(6)
        self.qp_table.setHorizontalHeaderLabels(["Date", "Requested By", "Items", "Location", "Remarks", "Destination"])
        self.qp_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        qp_layout.addWidget(self.qp_table)
        self.tabs.addTab(self.qp_tab, "⚡ Quick Pull Activity")
        
        # Purchase Request Tab
        self.pr_tab = QWidget()
        pr_layout = QVBoxLayout(self.pr_tab)
        self.pr_table = QTableWidget()
        self.pr_table.setColumnCount(5)
        self.pr_table.setHorizontalHeaderLabels(["Date", "PR No.", "Department", "End-User", "Total Amount"])
        self.pr_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        pr_layout.addWidget(self.pr_table)
        self.tabs.addTab(self.pr_tab, "🛒 Purchase Request Logs")
        
        self.main_layout.addWidget(self.tabs)
        
        QTimer.singleShot(500, self.load_data)

    def load_data(self):
        with SessionLocal() as db:
            # Load Quick Pulls
            qp_logs = db.query(QuickPullLog).options(joinedload(QuickPullLog.pulled_items).joinedload(QuickPullItem.item),
                                                 joinedload(QuickPullLog.source_location)).order_by(QuickPullLog.date.desc()).all()
            self.qp_table.setRowCount(0)
            for log in qp_logs:
                row = self.qp_table.rowCount()
                self.qp_table.insertRow(row)
                self.qp_table.setItem(row, 0, QTableWidgetItem(log.date.strftime("%Y-%m-%d")))
                self.qp_table.setItem(row, 1, QTableWidgetItem(log.requested_by))
                items_str = ", ".join([f"{pi.item.name if pi.item else 'Deleted Item'} ({pi.quantity:.0f})" for pi in log.pulled_items])
                self.qp_table.setItem(row, 2, QTableWidgetItem(items_str))
                self.qp_table.setItem(row, 3, QTableWidgetItem(log.source_location.name if log.source_location else "N/A"))
                self.qp_table.setItem(row, 4, QTableWidgetItem(log.purpose or ""))
                self.qp_table.setItem(row, 5, QTableWidgetItem(log.destination or ""))

            # Load Purchase Requests
            pr_logs = db.query(PurchaseRequest).options(joinedload(PurchaseRequest.items)).order_by(PurchaseRequest.request_date.desc()).all()
            self.pr_table.setRowCount(0)
            for pr in pr_logs:
                row = self.pr_table.rowCount()
                self.pr_table.insertRow(row)
                self.pr_table.setItem(row, 0, QTableWidgetItem(pr.request_date.strftime("%Y-%m-%d")))
                self.pr_table.setItem(row, 1, QTableWidgetItem(pr.pr_no))
                self.pr_table.setItem(row, 2, QTableWidgetItem(pr.department))
                self.pr_table.setItem(row, 3, QTableWidgetItem(pr.end_user or ""))
                total = sum([item.total for item in pr.items])
                self.pr_table.setItem(row, 4, QTableWidgetItem(f"P{total:,.2f}"))

class ReportsAnalyticalHub(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #F5F6FA;")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Top Bar (Minimal)
        top_bar = QFrame()
        top_bar.setFixedHeight(60)
        top_bar.setStyleSheet("background-color: #FFFFFF; border-bottom: 1px solid #E1E4E8;")
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(30, 0, 30, 0)
        
        title = QLabel("Reports & Analytics")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2F3542;")
        top_bar_layout.addWidget(title)
        
        top_bar_layout.addStretch()
        
        # Export/Report Action (One primary button only)
        self.export_btn = QPushButton("Generate Report")
        self.export_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 18px;
                background-color: #4A90E2;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #357ABD; }
        """)
        self.export_btn.clicked.connect(self.run_analytics_report)
        top_bar_layout.addWidget(self.export_btn)
        
        self.main_layout.addWidget(top_bar)
        
        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #F5F6FA; }
            QTabBar::tab { 
                padding: 12px 25px; 
                background: transparent; 
                border: none;
                border-bottom: 2px solid transparent;
                font-weight: bold;
                font-size: 13px;
                color: #7f8c8d;
            }
            QTabBar::tab:selected { 
                color: #4A90E2; 
                border-bottom: 2px solid #4A90E2; 
            }
        """)
        
        # 1. Smart Inventory Analysis
        self.inventory_tab = InventoryAnalysisView()
        self.tabs.addTab(self.inventory_tab, "📦 Inventory Smart Analysis")
        
        # 2. Employee Smart Analysis
        self.employee_tab = EmployeeAnalysisView()
        self.tabs.addTab(self.employee_tab, "👥 Employee Usage Behavior")
        
        # 3. Quick Pull & Process Logs
        self.logs_tab = ActivityLogView()
        self.tabs.addTab(self.logs_tab, "⚡ Operational Logs Activity")
        
        # Ensure data refreshes automatically when switching between sub-tabs
        self.tabs.currentChanged.connect(self.load_data)
        
        self.main_layout.addWidget(self.tabs)

    def load_data(self):
        """Called when switching to this view in main.py"""
        idx = self.tabs.currentIndex()
        if idx == 0: self.inventory_tab.load_data()
        elif idx == 1: self.employee_tab.load_aggregate_data()
        elif idx == 2: self.logs_tab.load_data()

    def switch_to_tab(self, index):
        self.tabs.setCurrentIndex(index)
        self.load_data()

    def run_analytics_report(self):
        """Shows selection dialog and generates requested analytical report."""
        mode = "inventory" if self.tabs.currentIndex() == 0 else "employee"
        dialog = ReportSelectionDialog(mode, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            report_type = dialog.get_selected_report()
            export_format = dialog.get_export_format()
            if report_type:
                self.generate_specific_report(report_type, export_format)

    def generate_specific_report(self, report_type, export_format="excel"):
        from form_generator import (get_frequency_category, generate_high_frequency_report, 
                                   generate_pending_requests_report, generate_employee_behavior_report)
        
        try:
            with SessionLocal() as db:
                if report_type == "high_freq":
                    # 1. High Frequency Items
                    # Calculate average days between requests for each item
                    # This is a more complex query, let's simplify for the report for now
                    # For a true average frequency, we'd need to get all request dates for each item
                    # and calculate the average difference.
                    
                    # For now, let's get total quantity and count of requests
                    high_freq_data = db.query(Item.id, Item.name, func.sum(RequestItem.quantity).label("total_qty"), func.count(RequestItem.id).label("request_count")) \
                        .join(RequestItem, Item.id == RequestItem.item_id) \
                        .group_by(Item.id, Item.name).order_by(func.sum(RequestItem.quantity).desc()).all()

                    report_data = []
                    for item_id, name, total_qty, request_count in high_freq_data:
                        actual_stock = db.query(func.sum(Stock.quantity)).filter(Stock.item_id == item_id).scalar() or 0.0
                        total_qty_float = float(total_qty)
                        actual_stock_float = float(actual_stock)
                        lacking = max(0.0, total_qty_float - actual_stock_float)
                        report_data.append((name, total_qty_float, int(request_count), actual_stock_float, lacking)) 
                    
                    report_data.sort(key=lambda x: str(x[0]).lower())
                    
                    filename = f"HIGH_FREQUENCY_ITEMS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                    headers = ["Item Name", "Total Quantity Requested", "Total Request Count", "Actual Stock", "Lacking"]
                    filename = generate_html_report("📊 Highly Requested Items Analysis", headers, report_data, filename)
                    self._handle_output(filename, "📊 Highly Requested Items Analysis", headers, report_data, export_format)
                    
                elif report_type == "pending":
                    # 2. Pending Requests (Date <= Today)
                    today = datetime.now()
                    pending = db.query(SupplyRequest).join(RequestItem).join(Employee).join(Department) \
                        .filter(SupplyRequest.status == "PENDING", SupplyRequest.request_date <= today) \
                        .options(joinedload(SupplyRequest.requested_items).joinedload(RequestItem.item),
                                 joinedload(SupplyRequest.employee),
                                 joinedload(SupplyRequest.department)).all()
                    
                    report_data = []
                    for req in pending:
                        date_str = req.request_date.strftime("%Y-%m-%d")
                        emp_name = req.employee.name if req.employee else "N/A"
                        area = req.department.area_name if req.department else "N/A"
                        for ri in req.requested_items:
                            report_data.append((date_str, emp_name, ri.item.name, ri.quantity, area, req.status))
                    
                    if not report_data:
                        QMessageBox.information(self, "No Data", "No pending requests found for current or past dates.")
                        return
                    
                    # Sort alphabetically by employee name (first item is date, second is emp)
                    # or item name as requested? user said "names of the tem" (items)
                    report_data.sort(key=lambda x: str(x[2]).lower())
                        
                    filename = f"PENDING_REQUESTS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                    headers = ["Date", "Employee", "Item", "Quantity", "Area", "Status"]
                    filename = generate_html_report("⏳ Pending & Today's Requests", headers, report_data, filename, status_col_idx=5)
                    self._handle_output(filename, "⏳ Pending & Today's Requests", headers, report_data, export_format)
                    
                elif report_type == "behavior":
                    # 3. Consumption Analysis (Employee Behavior)
                    # Get all request items grouped by employee and item
                    behavior_query = db.query(Employee.name, Item.name, SupplyRequest.request_date) \
                        .join(SupplyRequest, Employee.id == SupplyRequest.employee_id) \
                        .join(RequestItem, SupplyRequest.id == RequestItem.request_id) \
                        .join(Item, RequestItem.item_id == Item.id) \
                        .order_by(Employee.name, Item.name, SupplyRequest.request_date).all()
                    
                    groups = {} # (emp, item) -> [dates]
                    for emp, item, date in behavior_query:
                        key = (emp, item)
                        if key not in groups: groups[key] = []
                        groups[key].append(date)
                    
                    report_data = []
                    for (emp, item), dates in groups.items():
                        total_qty = db.query(func.sum(RequestItem.quantity)) \
                            .join(SupplyRequest, RequestItem.request_id == SupplyRequest.id) \
                            .join(Employee, SupplyRequest.employee_id == Employee.id) \
                            .join(Item, RequestItem.item_id == Item.id) \
                            .filter(Employee.name == emp, Item.name == item).scalar() or 0
                            
                        last_date = dates[-1].strftime("%Y-%m-%d")
                        avg_gap = None
                        if len(dates) > 1:
                            gaps = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
                            avg_gap = sum(gaps) / len(gaps)
                        
                        freq_label = get_frequency_category(avg_gap)
                        gap_str = f"{avg_gap:.1f} days" if avg_gap is not None else "N/A"
                        report_data.append((emp, item, float(total_qty), last_date, gap_str, freq_label))
                    
                    report_data.sort(key=lambda x: str(x[1]).lower()) # Sort by item name
                    
                    filename = f"EMPLOYEE_BEHAVIOR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                    headers = ["Employee", "Item", "Total Qty", "Last Date", "Avg Days Between", "Frequency Classification"]
                    filename = generate_html_report("🧠 Supply Consumption Analysis", headers, report_data, filename)
                    self._handle_output(filename, "🧠 Supply Consumption Analysis", headers, report_data, export_format)
                    
                elif report_type == "individual_history":
                    # 4. Individual Employee History (Consolidated from EmployeeAnalysisView)
                    items = self.employee_tab.emp_list.selectedItems()
                    if not items:
                        QMessageBox.warning(self, "Selection Required", "Please select an employee first in the 'Employee Usage Behavior' tab.")
                        return
                    
                    self.employee_tab.run_employee_export() # Reuse the existing logic
                    return # Already handled inside run_employee_export

                elif report_type == "item_history":
                    # 5. Filter by Specific Item (New)
                    items_query = db.query(Item).order_by(Item.name).all()
                    dialog = ItemSelectionDialog(items_query, self)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        selected_items = dialog.get_selected_items()
                        if not selected_items:
                            QMessageBox.warning(self, "Selection Required", "Please select at least one item.")
                            return
                        
                        item_ids = [it.id for it in selected_items]
                        item_names = [it.name for it in selected_items]
                        
                        # Query history for the selected item(s) across all employees
                        history = db.query(Employee.name, SupplyRequest.request_date, RequestItem.quantity, Item.name, Item.description, Department.area_name) \
                            .join(SupplyRequest, Employee.id == SupplyRequest.employee_id) \
                            .join(RequestItem, SupplyRequest.id == RequestItem.request_id) \
                            .join(Item, RequestItem.item_id == Item.id) \
                            .outerjoin(Department, SupplyRequest.department_id == Department.id) \
                            .filter(Item.id.in_(item_ids)) \
                            .order_by(SupplyRequest.request_date.desc()).all()
                        
                        if not history:
                            QMessageBox.information(self, "No Data", f"No requests found for: {', '.join(item_names)}")
                            return
                            
                        total_qty = sum(float(qty) for emp, date, qty, item, desc, area in history)
                        report_data = []
                        for emp, date, qty, item, desc, area in history:
                            report_data.append((emp, date.strftime("%Y-%m-%d %H:%M"), item, desc or "", float(qty), area or "N/A"))
                        
                        fname = f"ITEM_REQUEST_HISTORY_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                        headers = ["Employee Name", "Request Date", "Item Name", "Description", "Quantity", "Area/Dept"]
                        title = f"🔍 Request History for Selected Item(s)"
                        
                        metadata = {
                            "Filtered Items": ", ".join(item_names),
                            "Total Quantity Requested": f"{total_qty:.2f}",
                            "Record Count": f"{len(history)}"
                        }
                        
                        filename = generate_html_report(title, headers, report_data, fname, metadata=metadata)
                        self._handle_output(filename, title, headers, report_data, export_format)
                    else:
                        return

                # --- NEW INVENTORY REPORTS ---
                elif report_type in ["stock_summary", "need_restock", "distribution"]:
                    # from form_generator import generate_inventory_report # Removed, using generate_html_report
                    if report_type == "distribution":
                        data = db.query(Item.name, Location.name, Stock.quantity, Item.unit, Item.standard_stock) \
                            .join(Stock, Item.id == Stock.item_id) \
                            .join(Location, Stock.location_id == Location.id).all()
                        
                        report_data = []
                        for name, loc, qty, unit, custom_t in data:
                            status = evaluate_stock_status(unit, qty, custom_t)
                            report_data.append((name, loc, float(qty), unit, status))
                    else:
                        # Unify data source: Get items and their TOTAL stock across all locations
                        items_with_stock = db.query(Item, func.sum(Stock.quantity).label("total_qty")) \
                            .outerjoin(Stock, Item.id == Stock.item_id) \
                            .group_by(Item.id).all()
                        
                        report_data = []
                        for item, total_qty in items_with_stock:
                            total_qty = total_qty or 0.0
                            status = evaluate_stock_status(item.unit, total_qty, item.standard_stock)
                            
                            # Get effective threshold for display
                            display_threshold, _ = get_effective_threshold(item.unit, item.standard_stock)
                            
                            # Filter based on report type using the common status logic
                            if report_type == "need_restock" and status == "Need Restock":
                                report_data.append((item.name, item.description, float(total_qty), float(display_threshold), item.unit))
                            elif report_type == "stock_summary":
                                report_data.append((item.name, item.description, float(total_qty), float(display_threshold), item.unit))
                    
                    report_data.sort(key=lambda x: str(x[0]).lower())
                    
                    if not report_data:
                        QMessageBox.information(self, "No Data", "No items matched the criteria for this report.")
                        return
                        
                    # Title Mapping for HTML
                    titles = {
                        "stock_summary": "📊 Global Stock Summary",
                        "need_restock": "⚠️ Items Needing Restock (Below 50%)",
                        "distribution": "📍 Inventory Distribution Report",
                        "custom_items": "📌 Custom Selected Items Report"
                    }
                    report_title = titles.get(report_type, "Inventory Report")
                    fname = f"INVENTORY_{report_type.upper()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                    
                    if report_type == "distribution":
                        headers = ["Item Name", "Location", "Quantity", "Unit", "Status"]
                        filename = generate_html_report(report_title, headers, report_data, fname, status_col_idx=4)
                    else:
                        headers = ["Item Name", "Description", "Actual Stock", "Threshold (Standard)", "Unit"]
                        filename = generate_html_report(report_title, headers, report_data, fname)
                    
                    self._handle_output(filename, report_title, headers, report_data, export_format)

                elif report_type == "custom_items":
                    # --- NEW CUSTOM ITEM SELECTION REPORT ---
                    items_query = db.query(Item).order_by(Item.name).all()
                    dialog = ItemSelectionDialog(items_query, self)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        selected_items = dialog.get_selected_items()
                        if not selected_items:
                            QMessageBox.warning(self, "Selection Required", "Please select at least one item to generate the report.")
                            return
                        
                        # Use HTML for custom selection
                        fname = f"CUSTOM_ITEMS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                        headers = ["Item Name", "Description", "Actual Stock", "Threshold", "Unit"]
                        
                        report_data = []
                        for item in selected_items:
                            # Calculate total stock across all locations for this item
                            total_qty = db.query(func.sum(Stock.quantity)).filter(Stock.item_id == item.id).scalar() or 0.0
                            display_threshold, _ = get_effective_threshold(item.unit, item.standard_stock)
                            report_data.append((item.name, item.description, float(total_qty), float(display_threshold), item.unit))

                        report_data.sort(key=lambda x: str(x[0]).lower())
                        filename = generate_html_report("📌 Custom Selected Items Report", headers, report_data, fname)
                        self._handle_output(filename, "📌 Custom Selected Items Report", headers, report_data, export_format)
                    else:
                        return # User cancelled selection

                QMessageBox.information(self, "Success", f"Analytics report generated ({export_format.upper()})")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate analytics report: {e}")

    def _handle_output(self, html_filename, report_title, headers, report_data, export_format):
        if export_format == "excel":
            excel_fname = os.path.basename(html_filename).replace(".html", ".xlsx")
            filepath = generate_excel_report(report_title, headers, report_data, excel_fname)
            os.startfile(filepath)
        else:
            os.startfile(html_filename)

class ReportSelectionDialog(QDialog):
    def __init__(self, mode="employee", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setWindowTitle("Select Report Type")
        self.setFixedWidth(450)
        self.setStyleSheet("background-color: white; color: black;")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        header_text = "📋 Inventory Analytics Report" if mode == "inventory" else "📋 Employee Behavior Report"
        header = QLabel(header_text)
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2F3542;")
        layout.addWidget(header)
        
        desc = QLabel("Please select the type of analytics report you wish to generate:")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout.addWidget(desc)
        
        self.group = QButtonGroup(self)
        
        if mode == "inventory":
            options = [
                ("📊 Stock Summary Report", "stock_summary"),
                ("⚠️ Need Restock Items (Below 50%)", "need_restock"),
                ("📍 Inventory Distribution (By Location)", "distribution"),
                ("📌 Custom Item Report", "custom_items")
            ]
        else:
            options = [
                ("📊 Highly Requested Items", "high_freq"),
                ("⏳ Pending Requests (Past Due/Today)", "pending"),
                ("🧠 Consumption Analysis (Employee Behavior)", "behavior"),
                ("👤 Individual Employee History (Selected)", "individual_history"),
                ("🔍 Filter by Specific Item", "item_history")
            ]
            
        for i, (text, rtype) in enumerate(options):
            opt = QRadioButton(text)
            opt.setStyleSheet("font-size: 13px; padding: 5px;")
            opt.setProperty("type", rtype)
            if i == 0: opt.setChecked(True)
            self.group.addButton(opt)
            layout.addWidget(opt)
        
        layout.addWidget(QLabel("<b>Export Format:</b>"))
        format_layout = QHBoxLayout()
        self.excel_radio = QRadioButton("📊 Excel (Primary)")
        self.html_radio = QRadioButton("🌐 HTML Preview")
        self.excel_radio.setChecked(True)
        format_layout.addWidget(self.excel_radio)
        format_layout.addWidget(self.html_radio)
        layout.addLayout(format_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_report(self):
        button = self.group.checkedButton()
        if button:
            return button.property("type")
        return None

    def get_export_format(self):
        return "excel" if self.excel_radio.isChecked() else "html"

class ItemSelectionDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Items for Report")
        self.setFixedWidth(500)
        self.setFixedHeight(600)
        self.setStyleSheet("background-color: white; color: black;")
        self.all_items = items
        
        layout = QVBoxLayout(self)
        
        header = QLabel("📌 Custom Item Selection")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2F3542;")
        layout.addWidget(header)
        
        # Search Box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search items...")
        self.search_input.setStyleSheet("padding: 8px; border: 1px solid #ddd; border-radius: 4px;")
        self.search_input.textChanged.connect(self.filter_items)
        layout.addWidget(self.search_input)
        
        # List widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("border: 1px solid #eee; border-radius: 4px;")
        layout.addWidget(self.list_widget)
        
        self.populate_list()
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate_list(self, filter_text=""):
        self.list_widget.clear()
        for item in self.all_items:
            display_text = f"{item.name} - {item.description}" if item.description else item.name
            if filter_text.lower() in display_text.lower():
                list_item = QListWidgetItem(display_text)
                list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                list_item.setCheckState(Qt.CheckState.Unchecked)
                list_item.setData(Qt.ItemDataRole.UserRole, item) # Store the item object
                self.list_widget.addItem(list_item)

    def filter_items(self, text):
        # We need to preserve current check states if we filter?
        # For simplicity, let's just re-populate. 
        # Actually, it's better to hide/show items to preserve state.
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def get_selected_items(self):
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = QWidget()
    l = QVBoxLayout(window)
    h = ReportsAnalyticalHub()
    l.addWidget(h)
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec())
