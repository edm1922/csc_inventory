import sys
import os

# Add core and modules to search path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'core'))
sys.path.append(os.path.join(current_dir, 'modules'))

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget, QFrame)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont, QColor

# These are now found in sys.path (modules/ and core/)
from request_main import RequestTrackingApp
from inventory_main import InventoryManager
from purchase_main import PurchaseManager
from dashboard_main import SmartDashboard
from quick_pull_main import QuickPullManager
from database import init_db

class MainMenu(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.setSpacing(30)
        
        # Header
        header = QLabel("SUPPLY & INVENTORY SYSTEM")
        header.setStyleSheet("font-size: 32px; font-weight: bold; color: #1F4E78; margin-bottom: 20px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(header)
        
        subheader = QLabel("Select a module to continue")
        subheader.setStyleSheet("font-size: 18px; color: #555; margin-bottom: 40px;")
        subheader.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(subheader)
        
        # Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 1. Smart Analysis (NEW)
        self.smart_btn = self.create_menu_button(
            "📊", "Smart Analysis", 
            "Visual stats, stock alerts, and automated reports.",
            "#8e44ad"
        )
        self.smart_btn.clicked.connect(lambda: self.parent_window.switch_view(5))
        btn_layout.addWidget(self.smart_btn)

        # 2. Unified Request Button
        self.request_btn = self.create_menu_button(
            "🛰️", "Request Section", 
            "Track all office issuances and status.",
            "#2980b9"
        )
        self.request_btn.clicked.connect(lambda: self.parent_window.switch_view(1))
        btn_layout.addWidget(self.request_btn)
        
        # 3. Inventory Button
        self.inventory_btn = self.create_menu_button(
            "📋", "Inventory Manager", 
            "Manage stock levels and thresholds.",
            "#27ae60"
        )
        self.inventory_btn.clicked.connect(lambda: self.parent_window.switch_view(3))
        btn_layout.addWidget(self.inventory_btn)
        
        # 4. Purchase Request Button
        self.purchase_btn = self.create_menu_button(
            "🛒", "Purchase Request", 
            "Create and print formal Purchase Request forms.",
            "#e67e22"
        )
        self.purchase_btn.clicked.connect(lambda: self.parent_window.switch_view(4))
        btn_layout.addWidget(self.purchase_btn)
        
        # 5. Quick Pull Button (NEW)
        self.pull_btn = self.create_menu_button(
            "⚡", "Quick Pull Log", 
            "Fast item release log with auto-deduction.",
            "#d35400"
        )
        self.pull_btn.clicked.connect(lambda: self.parent_window.switch_view(2))
        btn_layout.addWidget(self.pull_btn)
        
        self.main_layout.addLayout(btn_layout)
        
        # Footer
        footer = QLabel("System v2.0 - Developed for Inventory Efficiency")
        footer.setStyleSheet("margin-top: 50px; color: #888; font-size: 12px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(footer)

    def create_menu_button(self, icon_char, title, description, color):
        btn = QPushButton()
        btn.setFixedSize(260, 200) # Slightly smaller to fit 4
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        btn_layout = QVBoxLayout(btn)
        
        icon_lbl = QLabel(icon_char)
        icon_lbl.setStyleSheet(f"font-size: 40px; color: {color}; background: transparent;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color}; background: transparent;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet("font-size: 11px; color: #666; background: transparent;")
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_layout.addWidget(icon_lbl)
        btn_layout.addWidget(title_lbl)
        btn_layout.addWidget(desc_lbl)
        
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                border: 2px solid #ddd;
                border-radius: 15px;
            }}
            QPushButton:hover {{
                border: 2px solid {color};
                background-color: #f9f9f9;
            }}
        """)
        
        return btn

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unified Inventory System")
        self.setMinimumSize(1200, 800)
        
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        self.menu_view = MainMenu(self)
        self.unified_request_view = RequestTrackingApp(mode="UNIFIED")
        self.inventory_view = InventoryManager()
        self.purchase_view = PurchaseManager()
        self.quick_pull_view = QuickPullManager()
        self.smart_view = SmartDashboard()
        
        # Add a "Back to Menu" button to the sub-views
        self.add_nav_bar(self.unified_request_view)
        self.add_nav_bar(self.inventory_view)
        self.add_nav_bar(self.purchase_view)
        self.add_nav_bar(self.quick_pull_view)
        self.add_nav_bar(self.smart_view)
        
        self.stack.addWidget(self.menu_view)               # 0
        self.stack.addWidget(self.unified_request_view)    # 1
        self.stack.addWidget(self.quick_pull_view)         # 2
        self.stack.addWidget(self.inventory_view)          # 3
        self.stack.addWidget(self.purchase_view)           # 4
        self.stack.addWidget(self.smart_view)              # 5
        
        self.stack.setCurrentIndex(0)

    def add_nav_bar(self, widget):
        if widget.layout():
            nav_layout = QHBoxLayout()
            back_btn = QPushButton("⬅ Back to Main Menu")
            back_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ecf0f1;
                    padding: 5px 15px;
                    border-radius: 5px;
                    font-weight: bold;
                    color: #2c3e50;
                }
                QPushButton:hover {
                    background-color: #bdc3c7;
                }
            """)
            back_btn.clicked.connect(lambda: self.switch_view(0))
            nav_layout.addWidget(back_btn)
            nav_layout.addStretch()
            widget.layout().insertLayout(0, nav_layout)

    def switch_view(self, index):
        self.stack.setCurrentIndex(index)
        if index == 1:
            self.unified_request_view.refresh_table()
        elif index == 2:
            self.quick_pull_view.load_logs()
        elif index == 3:
            self.inventory_view.load_data()
        elif index == 4:
            self.purchase_view.load_data()
        elif index == 5:
            self.smart_view.load_data()

if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
