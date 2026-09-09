# -*- coding: utf-8 -*-
from __future__ import annotations
"""
device_media_dialog.py — Device storage manager dialog.
Allows viewing, inspecting, and deleting media files stored on the player device.
"""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.ui.workers import DeleteMediaWorker, FetchMediaWorker


class DeviceMediaDialog(QDialog):
    def __init__(self, parent, client, playlists_manager=None):
        super().__init__(parent)
        self.client = client
        self.playlists_manager = playlists_manager
        self.setWindowTitle("Device Media Storage")
        self.resize(720, 500)

        self.layout = QVBoxLayout(self)

        # Info panel
        self.info_label = QLabel("Fetching media list...")
        self.info_label.setObjectName("label_section_title")
        self.layout.addWidget(self.info_label)

        # Media table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Filename", "Type", "Size", "MD5 ID"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setIconSize(QSize(48, 48))
        self.table.verticalHeader().setDefaultSectionSize(60)
        self.layout.addWidget(self.table)

        # Deletion progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.layout.addWidget(self.progress)

        # Action buttons
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("↻ Refresh")
        self.btn_refresh.setObjectName("btn_ghost")
        self.btn_refresh.clicked.connect(self.load_media)

        self.btn_delete = QPushButton("🗑 Delete Selected")
        self.btn_delete.setObjectName("btn_ghost")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self.delete_selected)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)

        self.layout.addLayout(btn_layout)

        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        self._active_worker = None
        self.load_media()

    def closeEvent(self, event):
        """Safe dialog closing with background worker termination."""
        if self._active_worker is not None:
            if hasattr(self._active_worker, "stop"):
                self._active_worker.stop()
            else:
                self._active_worker.quit()
                self._active_worker.wait(500)
        event.accept()

    def _on_selection_changed(self):
        has_selection = len(self.table.selectedItems()) > 0
        self.btn_delete.setEnabled(has_selection and self._active_worker is None)

    def load_media(self):
        if self._active_worker is not None:
            return

        self.btn_refresh.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.table.setRowCount(0)
        self.info_label.setText("Fetching media list...")

        self._active_worker = FetchMediaWorker(self.client, self.playlists_manager)
        self._active_worker.finished.connect(self._on_load_finished)
        self._active_worker.start()

    def _on_load_finished(self, success, medias, thumbnails_map, message):
        self._active_worker = None
        self.btn_refresh.setEnabled(True)
        self._on_selection_changed()

        if not success:
            self.info_label.setText(f"Error: {message}")
            return

        self.table.setRowCount(len(medias))
        total_size = 0

        for row, media in enumerate(medias):
            name = media.get("name", "Unknown")
            type_val = media.get("type", 1)
            size = media.get("size", 0)
            total_size += size
            md5_val = media.get("md5AndLength", "")

            type_str = "Video" if type_val == 1 else "Image"
            size_str = self._format_size(size)

            name_item = QTableWidgetItem(name)
            if md5_val in thumbnails_map:
                pixmap = QPixmap()
                pixmap.loadFromData(thumbnails_map[md5_val])
                name_item.setIcon(QIcon(pixmap))

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(type_str))
            self.table.setItem(row, 2, QTableWidgetItem(size_str))
            self.table.setItem(row, 3, QTableWidgetItem(md5_val))

        self.info_label.setText(f"Files: {len(medias)} | Total storage: {self._format_size(total_size)}")

    def delete_selected(self):
        if self._active_worker is not None:
            return

        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            return

        md5_list = []
        for row in selected_rows:
            item = self.table.item(row, 3)
            if item:
                md5_list.append(item.text())

        reply = QMessageBox.question(
            self,
            "Delete Media",
            f"Are you sure you want to delete {len(md5_list)} file(s) from the device?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.btn_refresh.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)

        self._active_worker = DeleteMediaWorker(self.client, md5_list)
        self._active_worker.progress.connect(self.progress.setValue)
        self._active_worker.finished.connect(self._on_delete_finished)
        self._active_worker.start()

    def _on_delete_finished(self, success, message):
        self._active_worker = None
        self.progress.setVisible(False)
        self.btn_refresh.setEnabled(True)

        if success:
            QMessageBox.information(self, "Success", message)
            self.load_media()
        else:
            QMessageBox.critical(self, "Error", message)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
