"""Brand colors (assets/brand/README.txt) and the Qt style sheet."""

from __future__ import annotations

INK = "#15131F"
PAPER = "#F7F4FA"
LIVE_PINK = "#FF4F8B"
HIGHLIGHT = "#FFD84D"

SURFACE = "#1D1A29"
SURFACE_2 = "#26223A"
BORDER = "#332E48"
MUTED = "#A39DB3"
PINK_LIGHT = "#FF7AA8"

STYLE_SHEET = f"""
* {{
    font-family: "Noto Sans KR", "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans CJK KR", sans-serif;
    color: {PAPER};
}}
QMainWindow, QDialog, QWidget#Root {{ background: {INK}; }}
QWidget#Card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
QWidget#Toolbar, QWidget#BottomBar {{ background: {SURFACE}; }}
QWidget#Toolbar {{ border-bottom: 1px solid {BORDER}; }}
QWidget#BottomBar {{ border-top: 1px solid {BORDER}; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#Eyebrow {{ color: {LIVE_PINK}; font-weight: 700; letter-spacing: 2px; font-size: 11px; }}
QLabel#Title {{ font-size: 22px; font-weight: 800; }}
QLabel#Status {{ color: {HIGHLIGHT}; font-weight: 600; }}
QLabel#Badge {{ background: {LIVE_PINK}; color: {INK}; border-radius: 6px; padding: 1px 6px; font-size: 10px; font-weight: 800; }}

QPushButton, QToolButton {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 6px 12px; font-weight: 600;
}}
QPushButton:hover, QToolButton:hover {{ background: #312C47; }}
QPushButton:pressed, QToolButton:pressed {{ background: #3A3454; }}
QPushButton:disabled, QToolButton:disabled {{ color: #6E6880; }}
QToolButton:checked, QPushButton:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {LIVE_PINK}, stop:1 {PINK_LIGHT});
    border-color: {LIVE_PINK}; color: {INK};
}}
QPushButton#Primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {LIVE_PINK}, stop:1 {PINK_LIGHT});
    border-color: {LIVE_PINK}; color: {INK}; font-weight: 800;
}}
QPushButton#Primary:hover {{ background: {PINK_LIGHT}; }}
QPushButton#BigAction {{
    font-size: 15px; font-weight: 800; padding: 18px 12px; border-radius: 12px; text-align: center;
}}
QPushButton#BigAction:hover {{ border-color: {LIVE_PINK}; }}

QToolButton#Swatch {{ border-radius: 9px; padding: 0; min-width: 18px; max-width: 18px; min-height: 18px; max-height: 18px; }}
QToolButton#Swatch:checked {{ border: 2px solid {PAPER}; }}

QSpinBox, QComboBox, QLineEdit, QDoubleSpinBox {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px 8px;
}}
QComboBox QAbstractItemView {{ background: {SURFACE_2}; selection-background-color: {LIVE_PINK}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {BORDER}; background: {SURFACE_2}; }}
QCheckBox::indicator:checked {{ background: {LIVE_PINK}; border-color: {LIVE_PINK}; }}
QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; margin: -6px 0; border-radius: 7px; background: {LIVE_PINK}; }}
QScrollArea {{ background: #100E18; border: none; }}
QScrollArea > QWidget > QWidget {{ background: #100E18; }}
QToolTip {{ background: {SURFACE_2}; color: {PAPER}; border: 1px solid {BORDER}; }}
QMessageBox {{ background: {INK}; }}
"""
