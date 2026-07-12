import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QInputDialog, QMessageBox, QFileDialog, QProgressDialog
)
from PyQt6.QtCore import Qt, QMimeData, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QColor, QBrush, QFont, QIcon, QPixmap

from src.core.config import screen_config, VIDEO_EXTENSIONS
from src.core.ffmpeg_renderer import FFmpegRenderer
from src.core.media_utils import (
    get_video_thumbnail_bytes,
    IMAGE_THUMBNAIL_EXTENSIONS,
    VIDEO_THUMBNAIL_EXTENSIONS,
)

class RenderWorker(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    
    def __init__(self, zones, rows, cols):
        super().__init__()
        self.zones = zones
        self.rows = rows
        self.cols = cols
        
    def run(self):
        try:
            renderer = FFmpegRenderer()
            out_file = renderer.render_scene(self.zones, self.rows, self.cols)
            self.finished_signal.emit(out_file)
        except Exception as e:
            self.error_signal.emit(str(e))

class SceneTableWidget(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ContiguousSelection)
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setIconSize(QSize(128, 128))
        self.setStyleSheet("""
            QTableWidget {
                background-color: #0f172a;
                gridline-color: #334155;
                border: 1px solid #334155;
                border-radius: 8px;
            }
            QTableWidget::item {
                border: 2px dashed #334155;
                border-radius: 8px;
            }
            QTableWidget::item:selected {
                background-color: rgba(16, 185, 129, 0.2);
                border: 2px solid #10b981;
            }
        """)

    def set_item_media(self, item: QTableWidgetItem, file_path: str):
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        name = Path(file_path).name
        ext = Path(file_path).suffix.lower()
        is_video = ext in VIDEO_EXTENSIONS
        icon_str = "🎬" if is_video else ""
        
        item.setText("")
        item.setIcon(QIcon())
        item.setBackground(QBrush(QColor(16, 185, 129, 38))) # rgba(16, 185, 129, 0.15)
        
        cell_widget = QWidget()
        cell_widget.setStyleSheet("background: transparent;")
        cell_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        layout = QHBoxLayout(cell_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Миниатюра: для картинок — QPixmap напрямую, для видео/GIF — через FFmpeg
        pixmap = None
        if ext in IMAGE_THUMBNAIL_EXTENSIONS:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                pixmap = None
        elif ext in VIDEO_THUMBNAIL_EXTENSIONS:
            thumb_bytes = get_video_thumbnail_bytes(file_path, 64, 64)
            if thumb_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(thumb_bytes)
                if pixmap.isNull():
                    pixmap = None
        
        if pixmap and not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                64, 64, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            icon_label = QLabel()
            icon_label.setPixmap(scaled_pixmap)
            layout.addWidget(icon_label)
        
        text_label = QLabel(f"{icon_str} {name}".strip())
        text_label.setStyleSheet("color: #f8fafc; font-weight: bold; font-size: 14px;")
        layout.addWidget(text_label)
        
        self.setCellWidget(item.row(), item.column(), cell_widget)

    def clear_item_media(self, item: QTableWidgetItem):
        r, c = item.row(), item.column()
        item.setData(Qt.ItemDataRole.UserRole, None)
        item.setIcon(QIcon())
        
        # КРИТИЧЕСКИЙ НЮАНС:
        # При удалении CellWidget через self.removeCellWidget() или замене на None, 
        # виджет не удаляется из памяти сразу, а становится "призраком" (остается на экране поверх таблицы).
        # Обязательно нужно вызвать deleteLater() у старого виджета перед удалением привязки к ячейке.
        old_widget = self.cellWidget(r, c)
        if old_widget:
            old_widget.deleteLater()
            
        self.removeCellWidget(r, c)
        
        row_span = self.rowSpan(r, c)
        col_span = self.columnSpan(r, c)
        
        if row_span > 1 or col_span > 1:
            item.setText(f"Объединенная Зона ({row_span}x{col_span})\nДвойной клик для выбора")
        else:
            item.setText(f"Зона ({r+1}, {c+1})\nДвойной клик для выбора")
            
        item.setBackground(QBrush(QColor(0, 0, 0, 0))) # Transparent 
        item.setForeground(QBrush(QColor("#475569")))
        font = item.font()
        font.setBold(False)
        item.setFont(font)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if urls:
            # КРИТИЧЕСКИЙ НЮАНС: 
            # Пути файлов при Drag-and-Drop (особенно на Windows) могут содержать 
            # невидимые символы переноса строки (\r\n) в конце. 
            # Функция .strip() обязательна, иначе проверка существования файла сломается.
            file_path = urls[0].toLocalFile().strip()
            item = self.itemAt(event.position().toPoint())
            if item:
                self.set_item_media(item, file_path)
            event.acceptProposedAction()

class SceneEditor(QWidget):
    """
    Визуальный редактор сцен (матрица экранов).
    Позволяет объединять экраны в зоны и назначать медиафайлы.
    """
    render_completed = pyqtSignal(str) # Signal emitted when render is done
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QHBoxLayout()
        title = QLabel("Визуальный редактор зон (Multi-layer)")
        title.setObjectName("label_title")
        header.addWidget(title)
        
        self.btn_merge = QPushButton("Объединить")
        self.btn_merge.setObjectName("btn_ghost")
        self.btn_merge.clicked.connect(self.merge_cells)
        header.addWidget(self.btn_merge)

        self.btn_split = QPushButton("Разделить")
        self.btn_split.setObjectName("btn_ghost")
        self.btn_split.clicked.connect(self.split_cells)
        header.addWidget(self.btn_split)

        self.btn_clear = QPushButton("Очистить")
        self.btn_clear.setObjectName("btn_ghost")
        self.btn_clear.clicked.connect(self.clear_media)
        header.addWidget(self.btn_clear)

        layout.addLayout(header)

        self.table = SceneTableWidget()
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.table)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        btn_save = QPushButton("Склеить и отправить на LED (FFmpeg)")
        btn_save.setObjectName("btn_primary")
        btn_save.setMinimumWidth(300)
        btn_save.clicked.connect(self.render_and_play)
        bottom_layout.addWidget(btn_save)
        
        layout.addLayout(bottom_layout)

        self.refresh_grid()

    def on_item_double_clicked(self, item: QTableWidgetItem):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите медиафайл для зоны",
            "",
            "Media Files (*.mp4 *.avi *.mkv *.png *.jpg *.jpeg)"
        )
        if file_path:
            self.table.set_item_media(item, file_path)

    def refresh_grid(self):
        self.table.clearSpans()
        rows = max(1, screen_config.rows)
        cols = max(1, screen_config.cols)
        
        self.table.setRowCount(rows)
        self.table.setColumnCount(cols)
        
        for r in range(rows):
            for c in range(cols):
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, c, item)
                self.table.clear_item_media(item)

    def merge_cells(self):
        selected = self.table.selectedRanges()
        if not selected:
            return
        
        range_ = selected[0]
        top_r = range_.topRow()
        left_c = range_.leftColumn()
        r_count = range_.rowCount()
        c_count = range_.columnCount()
        
        if r_count == 1 and c_count == 1:
            return
            
        self.table.setSpan(top_r, left_c, r_count, c_count)
        
        main_item = self.table.item(top_r, left_c)
        
        for r in range(top_r, top_r + r_count):
            for c in range(left_c, left_c + c_count):
                if r == top_r and c == left_c:
                    continue
                item = self.table.item(r, c)
                if item:
                    self.table.clear_item_media(item)
                           
        if main_item and not main_item.data(Qt.ItemDataRole.UserRole):
            self.table.clear_item_media(main_item) # Update text to show merged size

    def split_cells(self):
        selected = self.table.selectedRanges()
        if not selected:
            return
        range_ = selected[0]
        top_r = range_.topRow()
        left_c = range_.leftColumn()
        
        self.table.setSpan(top_r, left_c, 1, 1)
        
        for r in range(top_r, top_r + range_.rowCount()):
            for c in range(left_c, left_c + range_.columnCount()):
                item = self.table.item(r, c)
                if not item:
                    item = QTableWidgetItem()
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(r, c, item)
                
                if r == top_r and c == left_c:
                    if not item.data(Qt.ItemDataRole.UserRole):
                        self.table.clear_item_media(item)
                else:
                    self.table.clear_item_media(item)

    def clear_media(self):
        selected = self.table.selectedRanges()
        if not selected:
            return
            
        range_ = selected[0]
        for r in range(range_.topRow(), range_.topRow() + range_.rowCount()):
            for c in range(range_.leftColumn(), range_.leftColumn() + range_.columnCount()):
                item = self.table.item(r, c)
                if item:
                    self.table.clear_item_media(item)

    def render_and_play(self):
        zones = []
        rows = self.table.rowCount()
        cols = self.table.columnCount()
        
        processed = set()
        for r in range(rows):
            for c in range(cols):
                if (r, c) in processed:
                    continue
                    
                row_span = self.table.rowSpan(r, c)
                col_span = self.table.columnSpan(r, c)
                
                item = self.table.item(r, c)
                if item:
                    media = item.data(Qt.ItemDataRole.UserRole)
                    if media:
                        zones.append({
                            "row": r,
                            "col": c,
                            "rowSpan": row_span,
                            "colSpan": col_span,
                            "media": media
                        })
                
                for rr in range(r, r + row_span):
                    for cc in range(c, c + col_span):
                        processed.add((rr, cc))
                        
        if not zones:
            QMessageBox.warning(self, "Ошибка", "Нет зон с назначенными медиафайлами!")
            return
            
        self.progress = QProgressDialog("Идёт рендер сцены (FFmpeg)...", "Отмена", 0, 0, self)
        self.progress.setWindowTitle("Сборка видео")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setCancelButton(None) # Disable cancel for simplicity
        self.progress.show()
        
        self.worker = RenderWorker(zones, rows, cols)
        self.worker.finished_signal.connect(self._on_render_finished)
        self.worker.error_signal.connect(self._on_render_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_render_finished(self, out_file: str):
        self.progress.close()
        self.render_completed.emit(out_file)
        self.worker = None
        
    def _on_render_error(self, error: str):
        self.progress.close()
        QMessageBox.critical(self, "Ошибка FFmpeg", f"Произошла ошибка при сборке сцены:\n{error}")
        self.worker = None
