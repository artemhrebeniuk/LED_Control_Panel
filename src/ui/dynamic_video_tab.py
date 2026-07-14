# -*- coding: utf-8 -*-
"""
dynamic_video_tab.py — Вкладка адаптивного видеоплеера (Динамическое видео).
Принимает телеметрию (скорость автомобиля) по UDP на порту 28765 и меняет скорость
воспроизведения видео в реальном времени.
"""

import sys
import socket
import threading
import time
import cv2
import numpy as np
import os
import subprocess
from pathlib import Path

import logging
logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QFileDialog, QSizePolicy, QProgressBar,
    QGraphicsDropShadowEffect, QListView, QApplication, QCheckBox,
    QMenu
)
from src.core.ffmpeg_manager import get_ffmpeg_path
from src.core.config import DEVICE_IP


from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, QRect, QRectF, QPoint, QPointF,
    QObject, QEvent, QPropertyAnimation, QEasingCurve, QAbstractAnimation
)
from PyQt6.QtGui import (
    QImage, QPixmap, QPainter, QFont, QColor, QLinearGradient,
    QPen, QBrush, QPainterPath, QPolygon, QIcon
)

APP_STYLESHEET = """
QWidget#dynamic_video_tab {
    background-color: #09090B;
}

#controls_container {
    background-color: rgba(18, 18, 20, 240);
    border-top: 1px solid rgba(16, 185, 129, 60);
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
}

#header_label, #slider_label {
    color: #A1A1AA; 
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
}

#val_label {
    color: #FAFAFA;
    font-size: 16px;
    font-weight: 700;
    min-width: 55px;
}

#info_panel {
    background-color: rgba(24, 24, 27, 200);
    border-radius: 8px;
    border: 1px solid rgba(16, 185, 129, 80);
}

#speed_val {
    color: #FFFFFF;
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 1px;
}

#speed_unit {
    color: #10B981;
    font-size: 13px;
    font-weight: 700;
    margin-top: 6px;
    letter-spacing: 1px;
}

#frame_val {
    color: #A1A1AA;
    font-size: 12px;
    font-weight: 600;
    font-family: monospace;
    margin-top: 4px;
}

#action_btn {
    background-color: rgba(24, 24, 27, 255); 
    color: #FAFAFA;
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
#action_btn:hover { background-color: rgba(39, 39, 42, 255); border-color: rgba(255,255,255,60); }
#action_btn:pressed { background-color: #121214; }

#obd_btn {
    background-color: rgba(5, 150, 105, 20);
    color: #10B981;
    border: 1px solid #10B981;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
#obd_btn:hover {
    background-color: #10B981; 
    color: #121214;
}
#obd_btn:pressed { background-color: #047857; color: #FFFFFF; }

#proj_btn {
    background-color: rgba(24, 24, 27, 255); 
    color: #FAFAFA;
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
#proj_btn:hover { background-color: rgba(39, 39, 42, 255); border-color: rgba(255,255,255,60); }
#proj_btn:pressed { background-color: #121214; }

#proj_btn[active="true"] {
    background-color: rgba(5, 150, 105, 20);
    color: #10B981;
    border: 1px solid #10B981;
}
#proj_btn[active="true"]:hover {
    background-color: #10B981;
    color: #121214;
}

QComboBox {
    background-color: rgba(24, 24, 27, 255);
    color: #FAFAFA;
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 14px;
    font-weight: 600;
}
QComboBox:hover { border-color: #10B981; background-color: #18181B; }

QComboBox::drop-down {
    border: none;
    width: 34px;
}

QComboBox::down-arrow {
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #A1A1AA;
    width: 0;
    height: 0;
}

QComboBox::down-arrow:on {
    border-top: none;
    border-bottom: 5px solid #10B981;
}

#action_btn:disabled {
    background-color: rgba(24, 24, 27, 80);
    color: rgba(250, 250, 250, 40);
    border: 1px solid rgba(255, 255, 255, 10);
}

QSlider {
    min-height: 30px;
}
QSlider::groove:horizontal {
    border: none;
    height: 8px;
    background: rgba(255, 255, 255, 30);
    border-radius: 4px;
}
QSlider::sub-page:horizontal {
    background: #10B981;
    border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #FFFFFF;
    border: 2px solid #10B981;
    width: 18px;
    height: 18px;
    margin: -5px 0;
    border-radius: 9px;
}
QSlider::handle:horizontal:hover {
    background: #F0FDF4;
    border: 4px solid #047857;
    width: 20px;
    height: 20px;
    margin: -7px -1px;
    border-radius: 10px;
}
"""

class LoadingSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.start(16) # ~60 FPS
        self.setFixedSize(24, 24)

    def rotate(self):
        self.angle = (self.angle + 6) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect().adjusted(2, 2, -2, -2)
        
        pen = QPen(QColor(16, 185, 129, 30), 2.5)
        painter.setPen(pen)
        painter.drawEllipse(rect)
        
        pen.setColor(QColor("#10B981"))
        painter.setPen(pen)
        painter.drawArc(rect, -self.angle * 16, 120 * 16)

class DynamicProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0
        self.max_value = 100
        self.anim_offset = 0.0
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(25) # ~40 FPS

    def animate(self):
        if 0 < self.value < self.max_value:
            self.anim_offset += 1.2
            if self.anim_offset > 80:
                self.anim_offset = 0
            self.update()

    def setValue(self, val):
        self.value = max(0, min(val, self.max_value))
        self.update()

    def setRange(self, min_val, max_val):
        self.max_value = max_val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        h = rect.height()
        r = h / 2.0
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 23, 42, 220))
        painter.drawRoundedRect(rect, r, r)
        
        if self.max_value > 0 and self.value > 0:
            pct = self.value / self.max_value
            chunk_w = int(rect.width() * pct)
            
            if chunk_w >= 4:
                chunk_rect = QRect(0, 0, chunk_w, rect.height())
                
                grad = QLinearGradient(0, 0, rect.width(), 0)
                grad.setColorAt(0.0, QColor("#059669"))
                grad.setColorAt(0.5, QColor("#10B981"))
                grad.setColorAt(1.0, QColor("#34D399"))
                
                painter.setBrush(grad)
                painter.drawRoundedRect(chunk_rect, r, r)
                
                painter.save()
                clip_path = QPainterPath()
                clip_path.addRoundedRect(QRectF(chunk_rect), r, r)
                painter.setClipPath(clip_path)
                
                highlight_pen = QPen(QColor(255, 255, 255, 35), 5)
                highlight_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(highlight_pen)
                
                stripe_spacing = 40
                offset = int(self.anim_offset) % stripe_spacing
                for x in range(-stripe_spacing, chunk_w + stripe_spacing, stripe_spacing):
                    painter.drawLine(x + offset, -5, x + offset - 10, h + 5)
                
                painter.restore()

class UdpListener(QThread):
    def __init__(self, playback_thread, port: int = 28765):
        super().__init__()
        self.playback_thread = playback_thread
        self.port = port
        self.is_running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(2.0)
        try:
            self.sock.bind(('127.0.0.1', self.port))
            print(f"Listening for UDP on port {self.port}")
        except Exception as e:
            print(f"UDP Bind Error: {e}")

    def run(self):
        while self.is_running:
            try:
                data, addr = self.sock.recvfrom(1024)
                speed = float(data.decode('utf-8'))
                self.playback_thread.update_speed(speed)
            except socket.timeout:
                self.playback_thread.update_speed(0.0)
            except Exception:
                pass

    def stop(self):
        self.is_running = False
        try:
            self.sock.close()
        except:
            pass

class VideoLoader(QThread):
    progress_updated = pyqtSignal(int, str)
    finished_loading = pyqtSignal(list, float)
    error_occurred = pyqtSignal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.is_running = True

    def run(self):
        try:
            cap = cv2.VideoCapture(self.path)
            if not cap.isOpened():
                self.error_occurred.emit("Could not open video file.")
                return
                
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                total_frames = 1
                
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            
            cache = []
            frame_idx = 0
            
            while self.is_running:
                ret, frame = cap.read()
                if not ret:
                    break
                
                h_f, w_f = frame.shape[:2]
                max_dim = 640
                if w_f > max_dim or h_f > max_dim:
                    scale = max_dim / max(w_f, h_f)
                    new_w = int(w_f * scale)
                    new_h = int(h_f * scale)
                    frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    h_f, w_f = new_h, new_w
                    
                # Сохраняем кадры как сырые QImage в RAM, без сжатия в JPEG.
                # Это сохраняет 100% оригинального качества изображения и полностью убирает задержки
                # на декодирование во время воспроизведения (0% CPU на декодер).
                bytes_per_line = 3 * w_f
                qimg = QImage(frame.data, w_f, h_f, bytes_per_line, QImage.Format.Format_BGR888).copy()
                cache.append(qimg)
                    
                frame_idx += 1
                if frame_idx % 5 == 0:
                    prog = min(100, int((frame_idx / total_frames) * 100))
                    raw_size = w_f * h_f * 3
                    ram_mb = (len(cache) * raw_size) / (1024 * 1024)
                    self.progress_updated.emit(prog, f"Loading frames into RAM... {prog}% ({ram_mb:.0f} MB)")
            
            cap.release()
            
            if self.is_running:
                if len(cache) == 0:
                    self.error_occurred.emit("No frames could be extracted.")
                else:
                    self.finished_loading.emit(cache, fps)
                
        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        self.is_running = False

class PlaybackThread(QThread):
    frame_ready = pyqtSignal(QImage)
    info_updated = pyqtSignal(float, float, int, int)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.frames_cache = []
        self.total_frames = 0
        self.fps = 30.0
        
        self.current_frame_float = 0.0
        self.smoothed_speed = 0.0
        self.current_speed = 0.0
        self.last_speed = 0.0
        
        self.sensitivity = 1.0
        self.smoothing_alpha = 0.2
        self.mode = 0
        self.autoplay_playing = True
        
        self.is_braking = False
        self.last_clamped_speed = 0.0
        self.last_smoothed_speed = 0.0
        self.decel_counter = 0
        self.accel_counter = 0
        
        self.lock = threading.Lock()
        self.last_emitted_target = -1
        self.rewind_factor = 1.0
        
        self.last_packet_time = 0.0
        self.average_packet_interval = 0.1
        self.last_raw_speed = 0.0
        self.target_raw_speed = 0.0
        self.packet_received_time = 0.0
        self.last_loop_time = 0.0

    def update_speed(self, speed_val):
        with self.lock:
            now = time.time()
            if self.last_packet_time > 0:
                interval = now - self.last_packet_time
                if 0.02 < interval < 2.0:
                    self.average_packet_interval = self.average_packet_interval * 0.85 + interval * 0.15
            
            self.last_packet_time = now
            self.last_raw_speed = self.current_speed
            self.target_raw_speed = speed_val
            self.packet_received_time = now

    def update_settings(self, sensitivity, smoothing_alpha, mode):
        with self.lock:
            self.sensitivity = sensitivity
            self.smoothing_alpha = smoothing_alpha
            self.mode = mode

    def set_autoplay_state(self, playing: bool):
        with self.lock:
            self.autoplay_playing = playing

    def load_cache(self, cache, fps):
        with self.lock:
            self.frames_cache = cache
            self.total_frames = len(cache)
            self.fps = fps
            self.current_frame_float = 0.0
            self.last_emitted_target = -1

    def run(self):
        self.last_loop_time = time.time()
        while self.is_running:
            start_time = time.time()
            dt = start_time - self.last_loop_time
            self.last_loop_time = start_time
            if dt <= 0.0 or dt > 0.2:
                dt = 0.016
            
            target = -1
            qimg = None
            c_speed = 0.0
            c_total = 0
            
            with self.lock:
                if self.total_frames == 0 or not self.frames_cache:
                    pass
                else:
                    self.last_speed = self.current_speed
                    self.last_smoothed_speed = self.smoothed_speed
                    
                    if self.packet_received_time > 0:
                        t_elapsed = time.time() - self.packet_received_time
                        if self.average_packet_interval > 0:
                            fraction = min(1.0, t_elapsed / self.average_packet_interval)
                        else:
                            fraction = 1.0
                        self.current_speed = self.last_raw_speed + (self.target_raw_speed - self.last_raw_speed) * fraction
                    else:
                        self.current_speed = self.target_raw_speed
                    
                    self.smoothed_speed += (self.current_speed - self.smoothed_speed) * self.smoothing_alpha
                    
                    clamped_speed = max(0.0, self.smoothed_speed)
                    base_rate = self.fps * dt
                    direction = 1.0
                    
                    if self.mode in (0, 3, 4):
                        acceleration = self.smoothed_speed - self.last_smoothed_speed
                        if abs(acceleration) < 0.002:
                            direction = 1.0
                        else:
                            direction = 1.0 if acceleration >= 0 else -1.0
                            
                        if self.mode == 3:
                            if direction < 0:
                                self.decel_counter += 1
                                self.accel_counter = 0
                                if self.decel_counter >= 5:
                                    self.is_braking = True
                            else:
                                self.accel_counter += 1
                                self.decel_counter = 0
                                if self.accel_counter >= 15:
                                    self.is_braking = False
                            
                        speed_multiplier = (clamped_speed / 30.0) ** 0.65
                        
                        if self.mode == 3 and self.is_braking:
                            speed_multiplier = max(0.4, min(1.2, speed_multiplier))
                            
                        delta_frames = base_rate * speed_multiplier * self.sensitivity * direction
                    elif self.mode == 1:
                        speed_multiplier = (clamped_speed / 30.0) ** 0.65
                        delta_frames = base_rate * speed_multiplier * self.sensitivity
                    else: # Mode 2: Autoplay
                        if self.autoplay_playing:
                            delta_frames = base_rate * self.sensitivity
                        else:
                            delta_frames = 0.0
                            
                    if self.mode != 2 and clamped_speed < 0.5:
                        mid_frame = self.total_frames / 2.0
                        if self.mode == 4:
                            if self.current_frame_float != mid_frame:
                                rewind_speed = base_rate * 1.5 * self.rewind_factor
                                if self.current_frame_float < mid_frame:
                                    self.current_frame_float = min(mid_frame, self.current_frame_float + rewind_speed)
                                else:
                                    self.current_frame_float = max(mid_frame, self.current_frame_float - rewind_speed)
                                self.rewind_factor = min(10.0, self.rewind_factor + 0.03)
                            else:
                                delta_frames = 0.0
                                self.rewind_factor = 1.0
                        else:
                            if self.current_frame_float > 0.0:
                                rewind_speed = base_rate * 1.5 * self.rewind_factor
                                delta_frames = -rewind_speed
                                self.current_frame_float = max(0.0, self.current_frame_float + delta_frames)
                                self.rewind_factor = min(10.0, self.rewind_factor + 0.03)
                            else:
                                delta_frames = 0.0
                                self.current_frame_float = 0.0
                                self.rewind_factor = 1.0
                    else:
                        self.rewind_factor = 1.0
                        mid_frame = self.total_frames / 2.0
                        
                        if self.mode == 4:
                            self.current_frame_float += delta_frames
                            if direction < 0:
                                if self.current_frame_float <= 0.0:
                                    self.current_frame_float = mid_frame
                            else:
                                if self.current_frame_float >= self.total_frames:
                                    self.current_frame_float = mid_frame
                        elif self.mode == 3 and direction < 0:
                            self.current_frame_float += delta_frames
                            self.current_frame_float = max(0.0, self.current_frame_float)
                        else:
                            self.current_frame_float += delta_frames
                            self.current_frame_float %= self.total_frames
                            
                    self.last_clamped_speed = clamped_speed
                    target = int(self.current_frame_float)
                    c_speed = self.smoothed_speed
                    c_total = self.total_frames
                    
                    if target != self.last_emitted_target and 0 <= target < self.total_frames:
                        qimg = self.frames_cache[target]
            
            if qimg is not None:
                self.frame_ready.emit(qimg)
                self.last_emitted_target = target
                self.info_updated.emit(c_speed, delta_frames, target, c_total)
            
            elapsed = time.time() - start_time
            sleep_time = max(0, 0.016 - elapsed)
            time.sleep(sleep_time)

    def stop(self):
        self.is_running = False

class VideoDisplayWidget(QWidget):
    clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.text = "Перетащите сюда видео для динамического режима"
        self.loading_overlay = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.loading_overlay:
            self.loading_overlay.resize(self.size())

    def set_image(self, img):
        self.image = img
        self.update()

    def set_text(self, text):
        self.text = text
        self.image = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0b0c10"))
        if self.image and not self.image.isNull():
            w, h = self.width(), self.height()
            iw, ih = self.image.width(), self.image.height()
            
            scaled_w = w
            scaled_h = int(ih * w / iw)
            if scaled_h > h:
                scaled_h = h
                scaled_w = int(iw * h / ih)
                
            x = (w - scaled_w) // 2
            y = (h - scaled_h) // 2
            
            painter.drawImage(QRect(x, y, scaled_w, scaled_h), self.image)
        else:
            painter.setPen(QColor("#a1a7c4"))
            font = QFont()
            font.setPointSize(18)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)

class UpwardPopupFilter(QObject):
    def __init__(self, combobox, popup):
        super().__init__(popup)
        self.combobox = combobox
        self.popup = popup
        self.is_positioning = False
        self.animation = None
        self.target_geom = None

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
            if self.animation and self.animation.state() == QAbstractAnimation.State.Running:
                return False
                
            if not self.is_positioning:
                self.is_positioning = True
                rect = self.combobox.rect()
                pos = self.combobox.mapToGlobal(rect.topLeft())
                popup_height = self.popup.height()
                if event.type() == QEvent.Type.Resize:
                    popup_height = event.size().height()
                new_y = pos.y() - popup_height - 4
                
                self.target_geom = QRect(pos.x(), new_y, self.popup.width(), popup_height)
                self.popup.move(pos.x(), new_y)
                self.is_positioning = False
                if event.type() == QEvent.Type.Move:
                    return True
                    
        elif event.type() == QEvent.Type.Show:
            if self.target_geom:
                rect = self.combobox.rect()
                pos = self.combobox.mapToGlobal(rect.topLeft())
                start_geom = QRect(self.target_geom.x(), pos.y() - 4, self.target_geom.width(), 0)
                
                self.is_positioning = True
                self.popup.setGeometry(start_geom)
                self.is_positioning = False
                
                self.animation = QPropertyAnimation(self.popup, b"geometry")
                self.animation.setDuration(160)
                self.animation.setStartValue(start_geom)
                self.animation.setEndValue(self.target_geom)
                self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
                self.animation.start()
                
        return super().eventFilter(obj, event)

class UpwardComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.popup_filter = None

    def showPopup(self):
        old_effects = QApplication.isEffectEnabled(Qt.UIEffect.UI_AnimateCombo)
        QApplication.setEffectEnabled(Qt.UIEffect.UI_AnimateCombo, False)
        
        self.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view().setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        popup = self.view().window()
        container = self.view().parentWidget()
        
        for widget in (popup, container):
            if widget:
                widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                if widget.isWindow():
                    widget.setWindowFlags(widget.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
                widget.setObjectName("TransparentPopupContainer")
                widget.setStyleSheet("QWidget#TransparentPopupContainer { background: transparent; border: none; }")
        
        if not self.popup_filter:
            self.popup_filter = UpwardPopupFilter(self, popup)
            popup.installEventFilter(self.popup_filter)
            
        super().showPopup()
        QApplication.setEffectEnabled(Qt.UIEffect.UI_AnimateCombo, old_effects)

class ExternalVideoWindow(QWidget):
    closed_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OBD Video Projection")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(400, 225)
        
        # Load local logo for window icon
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        
        self.image = None
        self.drag_start_pos = None
        self.window_start_geo = None
        self.is_resizing = False
        self.setMouseTracking(True)

    def set_image(self, img):
        self.image = img
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#000000"))
        
        if self.image and not self.image.isNull():
            w, h = self.width(), self.height()
            iw, ih = self.image.width(), self.image.height()
            
            scaled_w = w
            scaled_h = int(ih * w / iw)
            if scaled_h > h:
                scaled_h = h
                scaled_w = int(iw * h / ih)
                
            x = (w - scaled_w) // 2
            y = (h - scaled_h) // 2
            
            painter.drawImage(QRect(x, y, scaled_w, scaled_h), self.image)
        else:
            painter.setPen(QColor("#10B981"))
            font = QFont("Segoe UI", 13)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "PROJECTOR MODE ACTIVE\nDouble-click to Maximize")
            
        if not self.isFullScreen():
            painter.setPen(QPen(QColor(16, 185, 129, 60), 2))
            painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(16, 185, 129, 150))
            w, h = self.width(), self.height()
            grip = QPolygon([
                QPoint(w - 15, h),
                QPoint(w, h - 15),
                QPoint(w, h)
            ])
            painter.drawPolygon(grip)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            w, h = self.width(), self.height()
            
            if pos.x() >= w - 20 and pos.y() >= h - 20:
                self.is_resizing = True
            else:
                self.is_resizing = False
                
            self.drag_start_pos = event.globalPosition().toPoint()
            self.window_start_geo = self.geometry()
            event.accept()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        w, h = self.width(), self.height()
        
        if not self.isFullScreen() and pos.x() >= w - 20 and pos.y() >= h - 20:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor if not self.isFullScreen() else Qt.CursorShape.ArrowCursor)
            
        if event.buttons() & Qt.MouseButton.LeftButton:
            if self.drag_start_pos is not None:
                delta = event.globalPosition().toPoint() - self.drag_start_pos
                if self.is_resizing:
                    new_w = max(self.minimumWidth(), self.window_start_geo.width() + delta.x())
                    new_h = max(self.minimumHeight(), self.window_start_geo.height() + delta.y())
                    self.resize(new_w, new_h)
                else:
                    self.move(self.window_start_geo.topLeft() + delta)
                event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None
        self.window_start_geo = None
        self.is_resizing = False
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_fullscreen()
            event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.toggle_fullscreen()
            else:
                self.close()
            event.accept()
        elif event.key() == Qt.Key.Key_F:
            self.toggle_fullscreen()
            event.accept()
        else:
            super().keyPressEvent(event)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self.update()

    def closeEvent(self, event):
        self.closed_signal.emit()
        event.accept()

class DynamicVideoTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setObjectName("dynamic_video_tab")
        self.is_fullscreen = False
        self.loader_thread = None
        self.external_window = None
        self.obd_process = None
        
        self.init_ui()
        self.setStyleSheet(APP_STYLESHEET)
        
        self.playback_thread = PlaybackThread()
        self.playback_thread.frame_ready.connect(self.on_frame_ready)
        self.playback_thread.info_updated.connect(self.on_info_updated)
        self.playback_thread.start()

        self.udp_listener = UdpListener(self.playback_thread)
        self.udp_listener.start()
        
        self.obd_monitor_timer = QTimer(self)
        self.obd_monitor_timer.timeout.connect(self.monitor_obd_process)
        
        self.sens_slider.valueChanged.connect(self.sync_settings)
        self.smooth_slider.valueChanged.connect(self.sync_settings)
        self.mode_dropdown.currentIndexChanged.connect(self.sync_settings)
        self.sync_settings()

        self.setAcceptDrops(True)

    def sync_settings(self):
        sens_val = self.sens_slider.value() / 10.0
        smooth_val = self.smooth_slider.value() / 100.0
        mode_idx = self.mode_dropdown.currentIndex()
        
        if hasattr(self, 'play_pause_btn'):
            self.play_pause_btn.setEnabled(mode_idx == 2)
        
        if hasattr(self, 'sens_val_label'):
            self.sens_val_label.setText(f"{sens_val:.1f}x")
        if hasattr(self, 'smooth_val_label'):
            self.smooth_val_label.setText(f"{smooth_val:.2f}")
            
        self.playback_thread.update_settings(
            sensitivity=sens_val,
            smoothing_alpha=smooth_val,
            mode=mode_idx
        )

    def toggle_play_pause(self):
        is_playing = getattr(self, 'autoplay_is_playing', True)
        is_playing = not is_playing
        self.autoplay_is_playing = is_playing
        
        self.playback_thread.set_autoplay_state(is_playing)
        if is_playing:
            self.play_pause_btn.setText("⏸ PAUSE")
        else:
            self.play_pause_btn.setText("▶ PLAY")

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Video Display Widget
        self.video_display = VideoDisplayWidget(self)
        self.video_display.clicked.connect(self.open_file_dialog)
        self.main_layout.addWidget(self.video_display)

        # Loading Screen Overlay
        self.loading_widget = QWidget(self.video_display)
        self.video_display.loading_overlay = self.loading_widget
        self.loading_widget.setStyleSheet("background-color: rgba(11, 15, 25, 220);")
        self.loading_layout = QVBoxLayout(self.loading_widget)
        self.loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.loading_panel = QWidget()
        self.loading_panel.setFixedSize(450, 160)
        self.loading_panel.setObjectName("loading_panel")
        self.loading_panel.setStyleSheet("""
            #loading_panel {
                background-color: rgba(30, 41, 59, 230);
                border: 1px solid rgba(56, 189, 248, 80);
                border-radius: 16px;
            }
        """)
        
        panel_layout = QVBoxLayout(self.loading_panel)
        panel_layout.setContentsMargins(20, 15, 20, 15)
        panel_layout.setSpacing(10)
        
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.loading_spinner = LoadingSpinner()
        title_row.addWidget(self.loading_spinner)
        
        self.load_label = QLabel("КЭШИРОВАНИЕ КАДРОВ...")
        self.load_label.setStyleSheet("""
            color: #38BDF8; 
            font-size: 13px; 
            font-weight: 900; 
            letter-spacing: 2px;
            background: transparent;
        """)
        self.load_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title_row.addWidget(self.load_label)
        panel_layout.addLayout(title_row)
        
        self.load_bar = DynamicProgressBar()
        self.load_bar.setFixedHeight(10)
        panel_layout.addWidget(self.load_bar)
        
        bottom_row = QHBoxLayout()
        self.load_stats_label = QLabel("ЗАГРУЗКА...")
        self.load_stats_label.setStyleSheet("""
            color: #94A3B8;
            font-size: 12px;
            font-weight: 700;
            background: transparent;
        """)
        self.load_stats_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        bottom_row.addWidget(self.load_stats_label)
        
        bottom_row.addStretch()
        
        self.load_pct_label = QLabel("0%")
        self.load_pct_label.setStyleSheet("""
            color: #FFFFFF; 
            font-size: 18px; 
            font-weight: 900;
            background: transparent;
        """)
        self.load_pct_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bottom_row.addWidget(self.load_pct_label)
        panel_layout.addLayout(bottom_row)
        
        load_shadow = QGraphicsDropShadowEffect(self)
        load_shadow.setBlurRadius(30)
        load_shadow.setColor(QColor(56, 189, 248, 40))
        load_shadow.setOffset(0, 0)
        self.loading_panel.setGraphicsEffect(load_shadow)
        
        self.loading_layout.addWidget(self.loading_panel)
        self.loading_widget.hide()

        # Controls Container
        self.controls_widget = QWidget(self)
        self.controls_widget.setObjectName("controls_container")
        controls_layout = QVBoxLayout(self.controls_widget)
        controls_layout.setContentsMargins(15, 12, 15, 12)
        controls_layout.setSpacing(10)
  
        # Top row: Video File, OBD Scanner, Projection, Mode Combobox, Play/Pause Button
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        
        self.load_btn = QPushButton("📂 Видеофайл")
        self.load_btn.setObjectName("action_btn")
        self.load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.load_btn.setFixedSize(180, 42)
        self.load_btn.clicked.connect(self.open_file_dialog)
        top_row.addWidget(self.load_btn)

        self.launch_obd_btn = QPushButton("🚀 Сканер OBD-II")
        self.launch_obd_btn.setObjectName("obd_btn")
        self.launch_obd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launch_obd_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.launch_obd_btn.setFixedSize(180, 42)
        self.launch_obd_btn.clicked.connect(self.launch_obd_scanner)
        
        obd_glow = QGraphicsDropShadowEffect(self)
        obd_glow.setBlurRadius(15)
        obd_glow.setColor(QColor(56, 189, 248, 80))
        obd_glow.setOffset(0, 0)
        self.launch_obd_btn.setGraphicsEffect(obd_glow)
        top_row.addWidget(self.launch_obd_btn)
        
        self.proj_btn = QPushButton("📺 Трансляция")
        self.proj_btn.setObjectName("proj_btn")
        self.proj_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.proj_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.proj_btn.setFixedSize(180, 42)
        self.proj_btn.clicked.connect(self.toggle_projection)
        top_row.addWidget(self.proj_btn)
  
        top_row.addStretch()

        mode_label = QLabel("Режим:")
        mode_label.setObjectName("header_label")
        top_row.addWidget(mode_label)

        self.mode_dropdown = UpwardComboBox()
        self.mode_dropdown.addItems([
            "1: Reversible (Dynamic)", 
            "2: Classic (Forward Only)",
            "3: Autoplay (Loop)",
            "4: Reversible (Clamp)",
            "5: Centered (Loop)"
        ])
        self.mode_dropdown.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_dropdown.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mode_dropdown.setFixedSize(240, 42)
        self.mode_dropdown.setView(QListView())
        
        combo_glow = QGraphicsDropShadowEffect(self)
        combo_glow.setBlurRadius(15)
        combo_glow.setColor(QColor(56, 189, 248, 30))
        combo_glow.setOffset(0, 0)
        self.mode_dropdown.setGraphicsEffect(combo_glow)
        top_row.addWidget(self.mode_dropdown)
        
        self.play_pause_btn = QPushButton("⏸ PAUSE")
        self.play_pause_btn.setObjectName("action_btn")
        self.play_pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_pause_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.play_pause_btn.setFixedSize(180, 42)
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.autoplay_is_playing = True
        
        play_glow = QGraphicsDropShadowEffect(self)
        play_glow.setBlurRadius(15)
        play_glow.setColor(QColor(56, 189, 248, 60))
        play_glow.setOffset(0, 0)
        self.play_pause_btn.setGraphicsEffect(play_glow)
        self.play_pause_btn.setEnabled(False) # По умолчанию отключена (активируется в Autoplay)
        top_row.addWidget(self.play_pause_btn)

        controls_layout.addLayout(top_row)

        # Bottom row: Sliders on the left, Telemetry Display (info_panel) on the right
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(20)
        
        # Sliders block (Vertical layout containing 2 horizontal layouts)
        sliders_layout = QVBoxLayout()
        sliders_layout.setSpacing(8)

        # Slider 1
        slider1_row = QHBoxLayout()
        sens_label = QLabel("Чувствительность")
        sens_label.setObjectName("slider_label")
        sens_label.setFixedWidth(170)
        slider1_row.addWidget(sens_label)

        self.sens_slider = QSlider(Qt.Orientation.Horizontal)
        self.sens_slider.setRange(1, 50)
        self.sens_slider.setValue(10)
        self.sens_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sens_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sens_slider.setMinimumWidth(500)
        slider1_row.addWidget(self.sens_slider)
        
        self.sens_val_label = QLabel("1.0x")
        self.sens_val_label.setObjectName("val_label")
        self.sens_val_label.setFixedWidth(55)
        slider1_row.addWidget(self.sens_val_label)
        sliders_layout.addLayout(slider1_row)

        # Slider 2
        slider2_row = QHBoxLayout()
        smooth_label = QLabel("Сглаживание")
        smooth_label.setObjectName("slider_label")
        smooth_label.setFixedWidth(170)
        slider2_row.addWidget(smooth_label)

        self.smooth_slider = QSlider(Qt.Orientation.Horizontal)
        self.smooth_slider.setRange(1, 100)
        self.smooth_slider.setValue(20)
        self.smooth_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.smooth_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.smooth_slider.setMinimumWidth(500)
        slider2_row.addWidget(self.smooth_slider)
        
        self.smooth_val_label = QLabel("0.20")
        self.smooth_val_label.setObjectName("val_label")
        self.smooth_val_label.setFixedWidth(55)
        slider2_row.addWidget(self.smooth_val_label)
        sliders_layout.addLayout(slider2_row)

        bottom_row.addLayout(sliders_layout)
        bottom_row.addStretch(1) # Создает свободное пространство (отступ) между слайдерами и панелью

        # Telemetry Display (info_panel)
        self.info_panel = QWidget()
        self.info_panel.setObjectName("info_panel")
        self.info_panel.setFixedWidth(320)
        self.info_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        self.info_glow = QGraphicsDropShadowEffect(self)
        self.info_glow.setBlurRadius(15)
        self.info_glow.setColor(QColor(56, 189, 248, 40))
        self.info_glow.setOffset(0, 0)
        self.info_panel.setGraphicsEffect(self.info_glow)
        info_layout = QHBoxLayout(self.info_panel)
        info_layout.setContentsMargins(10, 6, 10, 6)
        info_layout.setSpacing(4)
        
        self.speed_val_label = QLabel("0.0")
        self.speed_val_label.setObjectName("speed_val")
        self.speed_val_label.setFixedWidth(80)
        self.speed_val_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        info_layout.addWidget(self.speed_val_label)
        
        self.speed_unit_label = QLabel("KM/H")
        self.speed_unit_label.setObjectName("speed_unit")
        self.speed_unit_label.setFixedWidth(60)
        info_layout.addWidget(self.speed_unit_label)
        
        info_layout.addSpacing(4)
        
        self.frame_val_label = QLabel("FRAME: 0 / 0")
        self.frame_val_label.setObjectName("frame_val")
        self.frame_val_label.setFixedWidth(150)
        self.frame_val_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        info_layout.addWidget(self.frame_val_label)
        
        bottom_row.addWidget(self.info_panel, alignment=Qt.AlignmentFlag.AlignVCenter)

        controls_layout.addLayout(bottom_row)
        self.main_layout.addWidget(self.controls_widget)

        dash_shadow = QGraphicsDropShadowEffect(self)
        dash_shadow.setBlurRadius(30)
        dash_shadow.setColor(QColor(0, 0, 0, 180))
        dash_shadow.setOffset(0, -5)
        self.controls_widget.setGraphicsEffect(dash_shadow)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self.start_loading(files[0])
        event.acceptProposedAction()

    def open_file_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Video File", "", "Videos (*.mp4 *.avi *.mkv *.mov);;All Files (*)")
        if file_name:
            self.start_loading(file_name)

    def launch_obd_scanner(self):
        if self.obd_process is not None and self.obd_process.poll() is None:
            return
                
        try:
            project_root = Path(__file__).parents[2]
            main_py_path = project_root / "main.py"
            
            self.obd_process = subprocess.Popen(
                [sys.executable, str(main_py_path), "--run-obd-scanner"],
                cwd=str(project_root)
            )
                
            self.launch_obd_btn.setText("✅ СКАНЕР РАБОТАЕТ")
            self.launch_obd_btn.setStyleSheet("background-color: #10B981; color: #FFFFFF; border: 1px solid #10B981;")
            
            self.obd_monitor_timer.start(500)
        except Exception as e:
            self.video_display.set_text(f"Launch Error: {e}")

    def monitor_obd_process(self):
        if self.obd_process is not None:
            if self.obd_process.poll() is not None:
                self.obd_process = None
                self.obd_monitor_timer.stop()
                self.reset_obd_button()

    def reset_obd_button(self):
        self.launch_obd_btn.setText("🚀 СКАНЕР OBD-II")
        self.launch_obd_btn.setStyleSheet("")

    def start_loading(self, path):
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.stop()
            self.loader_thread.wait()
            
        self.loading_widget.show()
        self.load_bar.setValue(0)
        self.load_label.setText("КЭШИРОВАНИЕ КАДРОВ В RAM...")
        self.load_stats_label.setText("ПОДГОТОВКА КЭША...")
        self.load_pct_label.setText("0%")
        self.video_display.set_text("Кэширование video...")
        
        if self.external_window:
            self.external_window.set_image(None)
        
        self.loader_thread = VideoLoader(path)
        self.loader_thread.progress_updated.connect(self.on_load_progress)
        self.loader_thread.finished_loading.connect(self.on_load_finished)
        self.loader_thread.error_occurred.connect(self.on_load_error)
        self.loader_thread.start()

    def on_load_progress(self, prog, msg):
        self.load_bar.setValue(prog)
        if "(" in msg:
            stats_part = msg.split("(")[-1].replace(")", "")
            self.load_stats_label.setText(f"ОБЪЕМ: {stats_part}")
        else:
            self.load_stats_label.setText("КЭШИРОВАНИЕ ВИДЕО")
        self.load_pct_label.setText(f"{prog}%")

    def on_load_finished(self, cache, fps):
        self.loading_widget.hide()
        self.playback_thread.load_cache(cache, fps)
        
    def on_load_error(self, err_msg):
        self.loading_widget.hide()
        self.video_display.set_text(f"Ошибка: {err_msg}")

    def on_info_updated(self, smoothed_speed, delta_frames, current_frame, total_frames):
        self.frame_val_label.setText(f"КАДР: {current_frame} / {total_frames}")
        mode_idx = self.mode_dropdown.currentIndex()
        
        if mode_idx == 2:
            sens_val = self.sens_slider.value() / 10.0
            self.speed_val_label.setText(f"{sens_val:.1f}")
            self.speed_unit_label.setText("x")
            
            is_playing = getattr(self, 'autoplay_is_playing', True)
            if is_playing:
                color = "#10B981"
                glow = QColor(16, 185, 129, 60)
            else:
                color = "#F59E0B"
                glow = QColor(245, 158, 11, 60)
        else:
            self.speed_val_label.setText(f"{smoothed_speed:.1f}")
            self.speed_unit_label.setText("KM/H")
            
            if smoothed_speed < 30:
                color = "#38BDF8"
                glow = QColor(56, 189, 248, 60)
            elif smoothed_speed < 60:
                color = "#10B981"
                glow = QColor(16, 185, 129, 60)
            elif smoothed_speed < 90:
                color = "#F59E0B"
                glow = QColor(245, 158, 11, 60)
            else:
                color = "#EF4444"
                glow = QColor(239, 68, 68, 60)
            
        self.speed_val_label.setStyleSheet(f"color: {color};")
        self.speed_unit_label.setStyleSheet(f"color: {color};")
        if hasattr(self, 'info_glow') and self.info_glow:
            self.info_glow.setColor(glow)

    def on_frame_ready(self, qimg):
        self.video_display.set_image(qimg)
        if self.external_window and self.external_window.isVisible():
            self.external_window.set_image(qimg)

    def toggle_projection(self):
        if self.external_window is None:
            self.external_window = ExternalVideoWindow()
            self.external_window.closed_signal.connect(self.close_projection)
            
            if self.video_display.image:
                self.external_window.set_image(self.video_display.image)
                
            self.external_window.show()
            self.proj_btn.setProperty("active", "true")
            self.proj_btn.setText("📺 ТРАНСЛЯЦИЯ ВКЛ")
            self.proj_btn.style().unpolish(self.proj_btn)
            self.proj_btn.style().polish(self.proj_btn)
            
            self.proj_glow = QGraphicsDropShadowEffect(self)
            self.proj_glow.setBlurRadius(25)
            self.proj_glow.setColor(QColor(56, 189, 248, 120))
            self.proj_glow.setOffset(0, 0)
            self.proj_btn.setGraphicsEffect(self.proj_glow)
        else:
            self.close_projection()

    def close_projection(self):
        if self.external_window:
            try:
                self.external_window.closed_signal.disconnect(self.close_projection)
            except:
                pass
            self.external_window.close()
            self.external_window = None
            
        self.proj_btn.setProperty("active", "false")
        self.proj_btn.setText("📺 ТРАНСЛЯЦИЯ")
        self.proj_btn.setGraphicsEffect(None)
        self.proj_btn.style().unpolish(self.proj_btn)
        self.proj_btn.style().polish(self.proj_btn)

    def cleanup(self):
        if self.obd_process is not None:
            if self.obd_process.poll() is None:
                self.obd_process.terminate()
                
        if self.loader_thread:
            self.loader_thread.stop()
            self.loader_thread.wait()
            
        self.playback_thread.stop()
        self.playback_thread.wait()
        self.udp_listener.stop()
        self.udp_listener.wait()
