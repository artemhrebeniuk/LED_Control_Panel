# -*- coding: utf-8 -*-
from __future__ import annotations
"""
main.py — Entry point for Kystar KD6 LED Control Panel application.

Execution:
    python main.py

Dependencies:
    pip install PyQt6 requests
"""

import logging
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.ui.styles import STYLESHEET

# ====================================================================
# LOGGING CONFIGURATION
# ====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    """
    Initializes and launches the PyQt6 application.
    """
    if "-h" in sys.argv or "--help" in sys.argv:
        print("Usage: python main.py [OPTIONS]")
        print("\nOptions:")
        print("  -h, --help           Show this help message and exit")
        print("  --run-obd-scanner    Launch standalone OBD-II Diagnostics & CAN Scanner")
        sys.exit(0)

    if "--run-obd-scanner" in sys.argv:
        from src.ui.obd_gui_qt import OBDDashboardQT
        app = QApplication(sys.argv)
        window = OBDDashboardQT()
        window.show()
        sys.exit(app.exec())

    # Create Qt application instance
    app = QApplication(sys.argv)

    # Apply global Dark Mode styles from styles.py
    app.setStyleSheet(STYLESHEET)

    # Check for FFmpeg availability
    from src.core.ffmpeg_manager import is_ffmpeg_available
    if not is_ffmpeg_available():
        from PyQt6.QtWidgets import QMessageBox
        from src.ui.ffmpeg_download_dialog import FFmpegDownloadDialog
        
        reply = QMessageBox.question(
            None, 
            "FFmpeg Missing", 
            "Multi-zone layout mode (visual editor) requires the FFmpeg video engine.\n"
            "Unfortunately, it was not found on your system.\n\n"
            "Would you like to download and install it automatically now? (~130 MB)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            dialog = FFmpegDownloadDialog()
            dialog.exec()
        else:
            QMessageBox.warning(
                None, 
                "Limited Mode", 
                "The application will start, but visual editor compositing features may not function."
            )

    # Instantiate and display main window
    window = MainWindow()
    window.show()

    # Start main Qt event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
