# -*- coding: utf-8 -*-
from __future__ import annotations
"""
styles.py — QSS stylesheet for Kystar KD6 Control Panel.

Theme: Premium OLED Dark Mode (Flat Cards & Emerald Accents)
"""

# ====================================================================
# COLOR CONSTANTS
# ====================================================================
COLOR_BG_DEEPEST = "#09090B"  # zinc-950 (Deep background canvas)
COLOR_BG_PANEL = "#121214"    # Slightly lighter surface (panels / sections)
COLOR_BG_CARD = "#18181B"     # zinc-900 (Cards, buttons, inputs)
COLOR_BG_HOVER = "#27272A"    # zinc-800 (Hover states)

COLOR_ACCENT = "#10B981"      # emerald-500 (Primary accent action)
COLOR_ACCENT_HOVER = "#059669" # emerald-600 (Active/pressed accent)

COLOR_TEXT_PRIMARY = "#FAFAFA" # zinc-50
COLOR_TEXT_SECONDARY = "#A1A1AA" # zinc-400

COLOR_SUCCESS = "#10B981"
COLOR_ERROR = "#EF4444"
COLOR_WARNING = "#F59E0B"

COLOR_BORDER = "#27272A"      # zinc-800

# ====================================================================
# QSS STYLESHEET
# ====================================================================

STYLESHEET = f"""
/* ================================================================
   GLOBAL STYLES
   ================================================================ */

QMainWindow, QDialog {{
    background-color: {COLOR_BG_DEEPEST};
}}

QWidget {{
    color: {COLOR_TEXT_PRIMARY};
    font-family: "Inter", "Segoe UI", "Arial", sans-serif;
    font-size: 13px;
}}

QRadioButton, QCheckBox {{
    spacing: 8px;
    color: {COLOR_TEXT_PRIMARY};
}}

QRadioButton::indicator, QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {COLOR_BORDER};
    background-color: {COLOR_BG_CARD};
}}

QRadioButton::indicator {{
    border-radius: 8px;
}}

QCheckBox::indicator {{
    border-radius: 4px;
}}

QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
    background-color: {COLOR_ACCENT};
    border: 1px solid {COLOR_ACCENT};
}}

QTableWidget {{
    background-color: {COLOR_BG_PANEL};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    gridline-color: {COLOR_BORDER};
    color: {COLOR_TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {COLOR_BG_CARD};
    color: {COLOR_TEXT_SECONDARY};
    border: none;
    border-bottom: 1px solid {COLOR_BORDER};
    border-right: 1px solid {COLOR_BORDER};
    padding: 6px;
    font-weight: bold;
}}

QTableWidget::item:selected {{
    background-color: rgba(16, 185, 129, 0.2);
    color: {COLOR_TEXT_PRIMARY};
}}

/* ================================================================
   CARDS (Custom widget QWidget#card)
   ================================================================ */
QWidget#card {{
    background-color: {COLOR_BG_PANEL};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
}}

/* ================================================================
   TABS (QTabWidget)
   ================================================================ */

QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    background-color: {COLOR_BG_PANEL};
    border-radius: 8px;
    margin-top: -1px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {COLOR_TEXT_SECONDARY};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 10px 16px;
    font-weight: 500;
    font-size: 13px;
}}

QTabBar::tab:selected {{
    color: {COLOR_ACCENT};
    border-bottom: 2px solid {COLOR_ACCENT};
}}

QTabBar::tab:hover:!selected {{
    color: {COLOR_TEXT_PRIMARY};
    border-bottom: 2px solid {COLOR_BG_HOVER};
}}

/* ================================================================
   SCROLL AREA
   ================================================================ */

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {COLOR_BG_HOVER};
    min-height: 20px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_TEXT_SECONDARY};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* ================================================================
   BUTTONS (QPushButton)
   ================================================================ */

QPushButton {{
    background-color: {COLOR_BG_CARD};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    min-height: 32px;
}}

QPushButton:hover {{
    background-color: {COLOR_BG_HOVER};
    border-color: #3F3F46;
}}

QPushButton:pressed {{
    background-color: {COLOR_BG_PANEL};
}}

QPushButton:disabled {{
    background-color: {COLOR_BG_PANEL};
    color: {COLOR_TEXT_SECONDARY};
    border-color: {COLOR_BG_PANEL};
}}

/* Primary Action Button */
QPushButton#btn_primary,
QPushButton#btn_send_text,
QPushButton#btn_play_media {{
    background-color: {COLOR_ACCENT};
    border: none;
    color: {COLOR_BG_DEEPEST};
    font-weight: 600;
    min-height: 36px;
    font-size: 14px;
}}

QPushButton#btn_primary:hover,
QPushButton#btn_send_text:hover,
QPushButton#btn_play_media:hover {{
    background-color: #34d399; /* emerald-400 */
}}

QPushButton#btn_primary:pressed,
QPushButton#btn_send_text:pressed,
QPushButton#btn_play_media:pressed {{
    background-color: {COLOR_ACCENT_HOVER};
}}

/* Secondary Buttons (Ghost) */
QPushButton#btn_ghost {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT_PRIMARY};
}}

QPushButton#btn_ghost:hover {{
    background-color: {COLOR_BG_HOVER};
    border-color: {COLOR_TEXT_SECONDARY};
}}

/* Destructive / Warning Button (Red) */
QPushButton#btn_reboot, QPushButton#btn_delete {{
    background-color: transparent;
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: {COLOR_ERROR};
}}

QPushButton#btn_reboot:hover, QPushButton#btn_delete:hover {{
    background-color: rgba(239, 68, 68, 0.1);
    border-color: {COLOR_ERROR};
}}

/* Collapsible Log Toggle Button */
QPushButton#btn_toggle_logs {{
    background-color: transparent;
    border: none;
    color: {COLOR_TEXT_SECONDARY};
    font-size: 12px;
    font-weight: 500;
    text-align: left;
    padding: 4px 8px;
}}

QPushButton#btn_toggle_logs:hover {{
    color: {COLOR_TEXT_PRIMARY};
    background-color: {COLOR_BG_CARD};
    border-radius: 6px;
}}

/* ================================================================
   CONTAINERS & CARDS (QGroupBox)
   ================================================================ */

QGroupBox {{
    background-color: {COLOR_BG_PANEL};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    margin-top: 36px;
    padding-top: 16px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 4px;
    left: 8px;
    top: 2px;
    color: {COLOR_TEXT_SECONDARY};
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
}}

/* ================================================================
   INPUT FIELDS (QLineEdit, QSpinBox, QComboBox)
   ================================================================ */

QLineEdit, QSpinBox, QComboBox {{
    background-color: {COLOR_BG_DEEPEST};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    min-height: 28px;
    selection-background-color: rgba(16, 185, 129, 0.3);
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {COLOR_ACCENT};
    background-color: {COLOR_BG_PANEL};
}}

QLineEdit::placeholder {{
    color: {COLOR_TEXT_SECONDARY};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLOR_TEXT_SECONDARY};
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    selection-background-color: rgba(16, 185, 129, 0.2);
    selection-color: {COLOR_ACCENT};
    padding: 4px;
    outline: none;
}}

QSpinBox::up-button, QSpinBox::down-button {{
    background-color: transparent;
    width: 16px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {COLOR_BG_HOVER};
    border-radius: 2px;
}}

/* ================================================================
   BRIGHTNESS SLIDER (QSlider)
   ================================================================ */

QSlider {{
    min-height: 24px;
}}

QSlider::groove:horizontal {{
    background: {COLOR_BG_DEEPEST};
    height: 6px;
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: {COLOR_ACCENT};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: #ffffff;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background: #ffffff;
    border: 2px solid {COLOR_ACCENT};
}}

/* ================================================================
   LISTS (QListWidget)
   ================================================================ */

QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}

QListWidget::item {{
    background-color: {COLOR_BG_DEEPEST};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    margin: 2px 0px;
    color: {COLOR_TEXT_PRIMARY};
}}

QListWidget::item:selected {{
    background-color: rgba(16, 185, 129, 0.1);
    border: 1px solid {COLOR_ACCENT};
}}

QListWidget::item:hover {{
    background-color: {COLOR_BG_CARD};
}}

/* ================================================================
   PROGRESS BAR (QProgressBar)
   ================================================================ */

QProgressBar {{
    background-color: {COLOR_BG_DEEPEST};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent; 
}}

QProgressBar::chunk {{
    background-color: {COLOR_ACCENT};
    border-radius: 4px;
}}

/* ================================================================
   EVENT LOG (QTextEdit)
   ================================================================ */

QTextEdit#log_panel {{
    background-color: {COLOR_BG_DEEPEST};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 8px;
    font-family: "Consolas", monospace;
    font-size: 11px;
}}

/* ================================================================
   LABELS (QLabel)
   ================================================================ */

QLabel {{
    color: {COLOR_TEXT_PRIMARY};
    background: transparent;
}}

QLabel#label_secondary {{
    color: {COLOR_TEXT_SECONDARY};
    font-size: 12px;
}}

QLabel#label_section_title {{
    color: {COLOR_TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

QLabel#label_title {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}

QLabel#label_brightness_value {{
    color: {COLOR_ACCENT};
    font-size: 16px;
    font-weight: bold;
    min-width: 45px;
    alignment: right;
}}

QLabel#label_status_online {{
    color: {COLOR_ACCENT};
    font-weight: 600;
    font-size: 15px;
}}

QLabel#label_status_offline {{
    color: {COLOR_ERROR};
    font-weight: 600;
    font-size: 15px;
}}

/* ================================================================
   SEPARATOR
   ================================================================ */

QFrame#separator {{
    background-color: {COLOR_BORDER};
    max-height: 1px;
    border: none;
}}

/* ================================================================
   TOOLTIP
   ================================================================ */

QToolTip {{
    background-color: {COLOR_BG_CARD};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}}
"""

# ====================================================================
# DRAG-AND-DROP ZONE STYLING
# ====================================================================

DROP_ZONE_STYLE = f"""
    QLabel#drop_zone {{
        background-color: {COLOR_BG_DEEPEST};
        border: 1px dashed {COLOR_BG_HOVER};
        border-radius: 8px;
        color: {COLOR_TEXT_SECONDARY};
        font-size: 13px;
        padding: 20px;
        min-height: 60px;
    }}
"""

DROP_ZONE_HOVER_STYLE = f"""
    QLabel#drop_zone {{
        background-color: rgba(16, 185, 129, 0.05);
        border: 1px dashed {COLOR_ACCENT};
        border-radius: 8px;
        color: {COLOR_ACCENT};
        font-size: 13px;
        padding: 20px;
        min-height: 60px;
    }}
"""
