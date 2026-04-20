from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

CORPORATE_STYLESHEET = """
/* Global Application Style */
QMainWindow, QDialog, QWidget#centralWidget {
    background-color: #F5F7FA;
    font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
}

/* Button Styling */
QPushButton {
    background-color: #1E3A5F;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 11pt;
}

QPushButton:hover {
    background-color: #2C5282;
}

QPushButton:pressed {
    background-color: #1A365D;
}

QPushButton:disabled {
    background-color: #CBD5E0;
    color: #718096;
}

/* Table Styling */
QTableWidget {
    background-color: white;
    alternate-background-color: #F7FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    gridline-color: #EDF2F7;
    selection-background-color: #EBF4FF;
    selection-color: #1E3A5F;
    outline: none;
}

QHeaderView::section {
    background-color: #1E3A5F;
    color: white;
    padding: 10px;
    border: none;
    font-weight: bold;
    font-size: 10pt;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #EDF2F7;
}

/* Inputs & Form Elements */
QLineEdit, QComboBox, QDateEdit, QSpinBox {
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 8px 12px;
    background-color: white;
    color: #2D3748;
    selection-background-color: #BEE3F8;
}

QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
    border: 2px solid #2C7A7B;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    margin-top: 20px;
    padding-top: 20px;
    background-color: white;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 10px;
    color: #1E3A5F;
    left: 20px;
}

/* Tab Widget Styling */
QTabWidget::pane {
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    background: white;
    top: -1px;
}

QTabBar::tab {
    background-color: #EDF2F7;
    padding: 10px 20px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: #4A5568;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #1E3A5F;
    color: white;
    border-bottom: none;
}

QTabBar::tab:hover:!selected {
    background-color: #E2E8F0;
}

/* ScrollBar Styling */
QScrollBar:vertical {
    border: none;
    background: #F7FAFC;
    width: 10px;
    margin: 0px 0px 0px 0px;
}

QScrollBar::handle:vertical {
    background: #CBD5E0;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #A0AEC0;
}

/* Label Helpers */
QLabel#headerTitle {
    color: #1E3A5F;
    font-size: 20pt;
    font-weight: bold;
}

QLabel#statusReady {
    color: #718096;
    font-size: 9pt;
}

/* Card Styling */
.card {
    background-color: white;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
}
"""

def apply_corporate_theme(app: QApplication):
    """Applies the corporate design system to the entire application."""
    app.setStyleSheet(CORPORATE_STYLESHEET)
    
    # Global Font Setup
    corporate_font = QFont("Segoe UI", 10)
    app.setFont(corporate_font)

# Corporate Color Palette for Charts & UI Elements
CHART_COLORS = [
    "#1E3A5F", # Navy
    "#2C7A7B", # Teal
    "#D69E2E", # Gold
    "#4A5568", # Slate
    "#38A169", # Green
    "#E53E3E", # Red
    "#805AD5", # Purple
    "#3182CE", # Blue
]
