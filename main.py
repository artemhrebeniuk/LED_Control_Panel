# -*- coding: utf-8 -*-
"""
main.py — Точка входа приложения Kystar KD6 LED Control Panel.

Запуск:
    python main.py

Зависимости:
    pip install PyQt6 requests
"""

import logging
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.ui.styles import STYLESHEET

# ====================================================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    """
    Инициализирует и запускает приложение PyQt6.
    """
    if "--run-obd-scanner" in sys.argv:
        from src.ui.obd_gui_qt import OBDDashboardQT
        app = QApplication(sys.argv)
        window = OBDDashboardQT()
        window.show()
        sys.exit(app.exec())

    # Создаём экземпляр приложения Qt
    app = QApplication(sys.argv)

    # Применяем глобальные стили Dark Mode из styles.py
    app.setStyleSheet(STYLESHEET)

    # Проверка наличия FFmpeg
    from src.core.ffmpeg_manager import is_ffmpeg_available
    if not is_ffmpeg_available():
        from PyQt6.QtWidgets import QMessageBox
        from src.ui.ffmpeg_download_dialog import FFmpegDownloadDialog
        
        reply = QMessageBox.question(
            None, 
            "Отсутствует FFmpeg", 
            "Для работы многозонного режима (визуальный редактор) требуется видеодвижок FFmpeg.\n"
            "К сожалению, он не найден на вашем компьютере.\n\n"
            "Скачать и установить его автоматически сейчас? (Около 130 МБ)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            dialog = FFmpegDownloadDialog()
            dialog.exec()
        else:
            QMessageBox.warning(
                None, 
                "Ограниченный режим", 
                "Программа будет запущена, но функции визуального редактора могут не работать."
            )

    # Создаём и отображаем главное окно
    window = MainWindow()
    window.show()

    # Запускаем основной цикл обработки событий Qt
    # sys.exit() гарантирует корректный код возврата ОС
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
