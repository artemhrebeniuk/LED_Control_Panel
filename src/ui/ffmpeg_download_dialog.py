# -*- coding: utf-8 -*-
from __future__ import annotations
"""
ffmpeg_download_dialog.py — Dialog window for downloading FFmpeg binaries on Windows.
"""
import os
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
)

FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
TOOLS_DIR = Path("tools/ffmpeg/bin")


class FFmpegDownloadWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def run(self):
        try:
            self.progress.emit(0, "Starting FFmpeg download (~130 MB)...")

            TOOLS_DIR.mkdir(parents=True, exist_ok=True)
            temp_zip = Path(tempfile.gettempdir()) / "ffmpeg_temp.zip"

            # Download file with progress tracking
            with urllib.request.urlopen(FFMPEG_URL) as response:
                total_size = int(response.info().get("Content-Length", 0))
                downloaded = 0
                chunk_size = 8192

                with open(temp_zip, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 80)
                            self.progress.emit(
                                percent,
                                f"Downloading: {downloaded // (1024 * 1024)} of {total_size // (1024 * 1024)} MB",
                            )

            self.progress.emit(80, "Extracting archive...")

            # Extract required executables
            with zipfile.ZipFile(temp_zip, "r") as zip_ref:
                files_to_extract = ["ffmpeg.exe", "ffprobe.exe"]
                extracted = 0

                for member in zip_ref.namelist():
                    for exe_name in files_to_extract:
                        if member.endswith(f"bin/{exe_name}"):
                            source = zip_ref.open(member)
                            target_path = TOOLS_DIR / exe_name
                            with open(target_path, "wb") as target:
                                target.write(source.read())
                            extracted += 1
                            self.progress.emit(80 + (extracted * 10), f"Extracted {exe_name}...")

            # Remove temporary archive
            temp_zip.unlink(missing_ok=True)

            self.progress.emit(100, "Installation complete!")
            self.finished.emit(True, "Success")

        except Exception as e:
            self.finished.emit(False, str(e))


class FFmpegDownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FFmpeg Installation")
        self.setFixedSize(420, 150)

        # Disable close button during installation to prevent corruption
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)

        layout = QVBoxLayout(self)

        self.status_label = QLabel("Preparing download...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.worker = FFmpegDownloadWorker()
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)

        self.worker.start()

    def _on_progress(self, percent: int, text: str):
        self.progress_bar.setValue(percent)
        self.status_label.setText(text)

    def _on_finished(self, success: bool, msg: str):
        if success:
            QMessageBox.information(
                self,
                "Success",
                "FFmpeg successfully installed! Multi-zone scene rendering is now available.",
            )
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to download FFmpeg:\n{msg}\nPlease install FFmpeg manually.",
            )
            self.reject()
