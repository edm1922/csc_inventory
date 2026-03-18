import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget, QFrame)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont, QColor

# Import the existing modules
from request_main import RequestTrackingApp
from inventory_main import InventoryManager
from database import init_db

class MainMenu(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.setSpacing(30)
        
        # Header
        header = QLabel("SUPPLY & INVENTORY SYSTEM")
        header.setStyleSheet("font-size: 32px; font-weight: bold; color: #1F4E78; margin-bottom: 20px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(header)
        
        subheader = QLabel("Select a module to continue")
        subheader.setStyleSheet("font-size: 18px; color: #555; margin-bottom: 40px;")
        subheader.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(subheader)
        
        # Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(40)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Satellite Request Button
        self.request_btn = self.create_menu_button(
            "🛰️", "Satellite Office Request", 
            "Track employee issuances for satellite areas.",
            "#2980b9"
        )
        self.request_btn.clicked.connect(lambda: self.parent_window.switch_view(1))
        btn_layout.addWidget(self.request_btn)
        
        # Main Office Request Button
        self.main_office_btn = self.create_menu_button(
            "🏢", "Main Office Request", 
            "Log internal supplies for the main office storage.",
            "#8e44ad"
        )
        self.main_office_btn.clicked.connect(lambda: self.parent_window.switch_view(2))
        btn_layout.addWidget(self.main_office_btn)
        
        # Inventory Button
        self.inventory_btn = self.create_menu_button(
            "📋", "Inventory Manager", 
            "Manage stock levels, prices, and suppliers.",
            "#27ae60"
        )
        self.inventory_btn.clicked.connect(lambda: self.parent_window.switch_view(3))
        btn_layout.addWidget(self.inventory_btn)
        
        self.layout.addLayout(btn_layout)
        
        # Footer
        footer = QLabel("System v2.0 - Developed for Inventory Efficiency")
        footer.setStyleSheet("margin-top: 50px; color: #888; font-size: 12px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(footer)

    def create_menu_button(self, icon_char, title, description, color):
        btn = QPushButton()
        btn.setFixedSize(300, 200)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # We'll use a layout inside the button to style it
        btn_layout = QVBoxLayout(btn)
        
        icon_lbl = QLabel(icon_char)
        icon_lbl.setStyleSheet(f"font-size: 48px; color: {color}; background: transparent;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color}; background: transparent;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet("font-size: 12px; color: #666; background: transparent;")
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
        self.setMinimumSize(1100, 750)
        
        # Central Stacked Widget
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # Initialize Views
        self.menu_view = MainMenu(self)
        self.sat_request_view = RequestTrackingApp(mode="SATELLITE")
        self.main_request_view = RequestTrackingApp(mode="MAIN_OFFICE")
        self.inventory_view = InventoryManager()
        
        # Add a "Back to Menu" button to the sub-views
        self.add_nav_bar(self.sat_request_view)
        self.add_nav_bar(self.main_request_view)
        self.add_nav_bar(self.inventory_view)
        
        self.stack.addWidget(self.menu_view)          # 0
        self.stack.addWidget(self.sat_request_view)   # 1
        self.stack.addWidget(self.main_request_view)  # 2
        self.stack.addWidget(self.inventory_view)     # 3
        
        self.stack.setCurrentIndex(0)

    def add_nav_bar(self, widget):
        # Insert a navigation bar at the top of existing layouts
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
            
            # Insert at the top of the existing layout
            widget.layout().insertLayout(0, nav_layout)

    def switch_view(self, index):
        self.stack.setCurrentIndex(index)
        if index == 1:
            self.sat_request_view.refresh_table()
        elif index == 2:
            self.main_request_view.refresh_table()
        elif index == 3:
            self.inventory_view.load_data()

if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Modern global font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
