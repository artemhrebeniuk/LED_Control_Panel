"""
Диалоговое окно для скачивания FFmpeg.
"""
import os
import zipfile
import tempfile
import urllib.request
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
TOOLS_DIR = Path("tools/ffmpeg/bin")

class FFmpegDownloadWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def run(self):
        try:
            self.progress.emit(0, "Начало загрузки FFmpeg (около 130 МБ)...")
            
            TOOLS_DIR.mkdir(parents=True, exist_ok=True)
            temp_zip = Path(tempfile.gettempdir()) / "ffmpeg_temp.zip"
            
            # Скачивание файла с отображением прогресса
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
                            # Прогресс от 0 до 80%
                            percent = int((downloaded / total_size) * 80)
                            self.progress.emit(percent, f"Загрузка: {downloaded // (1024*1024)} из {total_size // (1024*1024)} МБ")
            
            self.progress.emit(80, "Распаковка архива...")
            
            # Извлечение нужных бинарников
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
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
                            self.progress.emit(80 + (extracted * 10), f"Извлечен {exe_name}...")
                            
            # Удаляем временный архив
            temp_zip.unlink(missing_ok=True)
            
            self.progress.emit(100, "Установка завершена!")
            self.finished.emit(True, "Успешно")
            
        except Exception as e:
            self.finished.emit(False, str(e))

class FFmpegDownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Установка FFmpeg")
        self.setFixedSize(400, 150)
        
        # Убираем кнопку закрытия, чтобы не прерывали процесс случайно
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        
        self.status_label = QLabel("Подготовка к скачиванию...")
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
            QMessageBox.information(self, "Успех", "FFmpeg успешно установлен! Теперь доступен мульти-зонный режим.")
            self.accept()
        else:
            QMessageBox.critical(self, "Ошибка", f"Не удалось скачать FFmpeg:\n{msg}\nПопробуйте установить вручную.")
            self.reject()
