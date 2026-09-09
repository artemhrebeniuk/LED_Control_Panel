# -*- coding: utf-8 -*-
from __future__ import annotations
"""
main_window.py — Main window of the Kystar KD6 Control Panel application.

This module contains ONLY PyQt6 UI logic:
- Widget creation and layout assembly
- User event handling (clicks, Drag-and-Drop, sliders)
- Worker thread lifecycle management for network operations
- UI updates responding to worker signals

All network communication logic is delegated to kystar_client.py and workers.py.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.config import (
    ALLOWED_EXTENSIONS,
    AUTO_GRID,
    AUTO_OPTIMIZE_VIDEO,
    BRIGHTNESS_DEBOUNCE_MS,
    CONNECTION_MODE,
    CRUSH_BLACKS,
    DEVICE_IP,
    IMAGE_EXTENSIONS,
    LIMIT_BITRATE,
    PANEL_HEIGHT,
    PANEL_WIDTH,
    PING_INTERVAL_MS,
    SCREEN_COLS,
    SCREEN_ROWS,
    VIDEO_EXTENSIONS,
    get_current_urls,
    save_hardware_config,
    screen_config,
)
from src.core.kystar_client import KystarClient
from src.core.media_utils import (
    IMAGE_THUMBNAIL_EXTENSIONS,
    VIDEO_THUMBNAIL_EXTENSIONS,
    get_video_thumbnail_bytes,
)
from src.core.playlists_manager import PlaylistsManager
from src.ui.device_media_dialog import DeviceMediaDialog
from src.ui.dynamic_video_tab import DynamicVideoTab
from src.ui.scene_editor import SceneEditor
from src.ui.styles import DROP_ZONE_HOVER_STYLE, DROP_ZONE_STYLE
from src.ui.workers import (
    BrightnessWorker,
    ClearMemoryWorker,
    PingPongWorker,
    PingWorker,
    RebootWorker,
    ScreenPowerWorker,
    UploadMediaWorker,
)

logger = logging.getLogger(__name__)


class DropZoneLabel(QLabel):
    """
    Drag-and-Drop file landing zone widget.

    Accepts dropped files matching ALLOWED_EXTENSIONS.
    Highlights border with neon glow upon drag hover.
    """

    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        self.main_window = parent
        self.setObjectName("drop_zone")
        self.setText("📁  Drag & Drop media files here\nor click to browse")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(DROP_ZONE_STYLE)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Highlights drop zone on drag hover."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(DROP_ZONE_HOVER_STYLE)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        """Restores default styling when cursor leaves."""
        self.setStyleSheet(DROP_ZONE_STYLE)

    def dropEvent(self, event: QDropEvent) -> None:
        """Processes dropped files."""
        self.setStyleSheet(DROP_ZONE_STYLE)
        urls = event.mimeData().urls()
        file_paths: list[str] = []
        for url in urls:
            path = url.toLocalFile()
            ext = Path(path).suffix.lower()
            if ext in ALLOWED_EXTENSIONS:
                file_paths.append(path)
            else:
                self.main_window.log(f"⚠ Skipped unsupported file: {Path(path).name}")
        if file_paths:
            self.main_window.add_media_files(file_paths)
        event.acceptProposedAction()

    def mousePressEvent(self, event) -> None:
        """Opens file selection dialog on click."""
        self.main_window.open_file_dialog()


class MainWindow(QMainWindow):
    """
    Main application window for Kystar KD6 LED display control.
    """

    def __init__(self) -> None:
        super().__init__()

        # Initialize API client (no synchronous network calls in constructor)
        self.client = KystarClient()

        # Active worker threads registry to prevent GC collection
        self._active_workers: list = []

        # Playlists manager
        self.playlists_manager = PlaylistsManager()
        self.current_program_id = None

        # Debounce timer for brightness slider
        self._brightness_timer = QTimer()
        self._brightness_timer.setSingleShot(True)
        self._brightness_timer.setInterval(BRIGHTNESS_DEBOUNCE_MS)
        self._brightness_timer.timeout.connect(self._send_brightness)

        # Pending brightness value for debounce
        self._pending_brightness: int = 100

        # Current screen power state
        self._screen_on: bool = True

        self._setup_ui()
        self._start_ping_worker()

    # ================================================================
    # UI SETUP & COMPOSITION
    # ================================================================

    def _setup_ui(self) -> None:
        """Builds and composes all UI widgets."""
        self.setWindowTitle("Kystar KD6 — LED Control Panel")

        # Application icon setup
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.setMinimumSize(900, 700)
        self.resize(1000, 900)

        # Central widget
        central_widget = QWidget()
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(20, 12, 20, 20)
        root_layout.setSpacing(20)

        self.left_layout = QVBoxLayout()
        root_layout.addLayout(self.left_layout)

        self.main_container = QVBoxLayout()
        self.main_container.setSpacing(12)
        root_layout.addLayout(self.main_container, stretch=1)

        # --- Playlists Section (Left Sidebar) ---
        self._create_playlists_section()

        # Tabs container
        self.tabs = QTabWidget()
        self.main_container.addWidget(self.tabs)

        self.tab_simple = QWidget()
        self.tab_simple_layout = QVBoxLayout(self.tab_simple)
        self.tabs.addTab(self.tab_simple, "Simple Mode (Playlists)")

        self.tab_scene = QWidget()
        self.tab_scene_layout = QVBoxLayout(self.tab_scene)
        self.tabs.addTab(self.tab_scene, "Multi-Zone Scene Editor (Multi-layer)")

        self.tab_dynamic_video = DynamicVideoTab(self)
        self.tabs.addTab(self.tab_dynamic_video, "Dynamic Video")

        # --- Header ---
        self._create_header()

        # --- Media Library Section ---
        self._create_media_section()

        # --- Brightness Section ---
        self._create_brightness_section()

        # --- Device Controls Section ---
        self._create_control_section()

        # --- Multi-Zone Scene Editor ---
        self.scene_editor = SceneEditor(self)
        self.scene_editor.render_completed.connect(self._on_render_completed)
        self.tab_scene_layout.addWidget(self.scene_editor)

        # --- Event Log ---
        self._create_log_section()

        self.setCentralWidget(central_widget)

        # Welcome message
        self.log("✦ Kystar KD6 Control Panel started")
        self.log(f"  Device: {DEVICE_IP}")

        # Refresh programs after widgets are ready
        self._refresh_programs_list()

    def _create_playlists_section(self) -> None:
        """Creates the playlist management sidebar on the left."""
        group = QWidget()
        group.setObjectName("card")
        group.setMaximumWidth(280)
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Programs (Playlists)")
        title.setObjectName("label_section_title")
        layout.addWidget(title)

        self.list_programs = QListWidget()
        self.list_programs.itemSelectionChanged.connect(self._on_program_selected)
        layout.addWidget(self.list_programs)

        btn_row = QHBoxLayout()
        self.btn_add_program = QPushButton("New")
        self.btn_add_program.setObjectName("btn_ghost")
        self.btn_add_program.clicked.connect(self._on_add_program)
        btn_row.addWidget(self.btn_add_program)

        self.btn_rename_program = QPushButton("Rename")
        self.btn_rename_program.setObjectName("btn_ghost")
        self.btn_rename_program.clicked.connect(self._on_rename_program)
        btn_row.addWidget(self.btn_rename_program)

        self.btn_delete_program = QPushButton("Delete")
        self.btn_delete_program.setObjectName("btn_delete")
        self.btn_delete_program.clicked.connect(self._on_delete_program)
        btn_row.addWidget(self.btn_delete_program)

        layout.addLayout(btn_row)
        group.setLayout(layout)

        group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.left_layout.addWidget(group)

        self.btn_hardware_settings = QPushButton("Hardware & Connection Settings")
        self.btn_hardware_settings.setObjectName("btn_ghost")
        self.btn_hardware_settings.clicked.connect(self._on_hardware_settings)
        self.left_layout.addWidget(self.btn_hardware_settings)

    def _create_header(self) -> None:
        """Creates header title and device online/offline indicator."""
        header_layout = QHBoxLayout()
        title_label = QLabel("KYSTAR KD6 CONTROL")
        title_label.setObjectName("label_title")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        self.status_indicator = QLabel("●  Checking...")
        self.status_indicator.setObjectName("label_status_offline")
        header_layout.addWidget(self.status_indicator)
        self.tab_simple_layout.addLayout(header_layout)

    def _create_media_section(self) -> None:
        """Creates media library section with Drag-and-Drop."""
        group = QWidget()
        group.setObjectName("card")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Media Library")
        title.setObjectName("label_section_title")
        layout.addWidget(title)

        self.drop_zone = DropZoneLabel(self)
        layout.addWidget(self.drop_zone)
        self.media_list = QListWidget()
        self.media_list.setIconSize(QSize(64, 64))
        self.media_list.itemDoubleClicked.connect(self._on_remove_media_item)
        layout.addWidget(self.media_list)

        btn_row = QHBoxLayout()
        self.btn_add_files = QPushButton("Add Files")
        self.btn_add_files.setObjectName("btn_ghost")
        self.btn_add_files.clicked.connect(self.open_file_dialog)
        btn_row.addWidget(self.btn_add_files)

        self.btn_clear_list = QPushButton("Clear List")
        self.btn_clear_list.setObjectName("btn_ghost")
        self.btn_clear_list.clicked.connect(self._on_clear_media_list)
        btn_row.addWidget(self.btn_clear_list)
        layout.addLayout(btn_row)

        play_row = QHBoxLayout()
        self.btn_play_media = QPushButton("Play on LED")
        self.btn_play_media.setObjectName("btn_primary")
        self.btn_play_media.clicked.connect(self._on_play_media)
        play_row.addWidget(self.btn_play_media, stretch=2)

        play_row.addWidget(QLabel("Photo Duration:"))
        self.spin_image_duration = QSpinBox()
        self.spin_image_duration.setRange(1, 3600)
        self.spin_image_duration.setValue(5)
        self.spin_image_duration.setSuffix(" s")
        play_row.addWidget(self.spin_image_duration, stretch=1)
        layout.addLayout(play_row)

        progress_layout = QHBoxLayout()
        self.upload_progress = QProgressBar()
        self.upload_progress.setVisible(False)
        progress_layout.addWidget(self.upload_progress)

        self.btn_cancel_upload = QPushButton("Cancel")
        self.btn_cancel_upload.setObjectName("btn_ghost")
        self.btn_cancel_upload.setVisible(False)
        self.btn_cancel_upload.clicked.connect(self._on_cancel_upload)
        progress_layout.addWidget(self.btn_cancel_upload)

        layout.addLayout(progress_layout)
        group.setLayout(layout)
        self.tab_simple_layout.addWidget(group)

    def _create_brightness_section(self) -> None:
        """Creates brightness slider control section."""
        group = QWidget()
        group.setObjectName("card")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 16)

        title = QLabel("Screen Brightness")
        title.setObjectName("label_section_title")
        layout.addWidget(title)

        slider_layout = QHBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(0, 100)
        self.brightness_slider.setValue(100)
        self.brightness_slider.valueChanged.connect(self._on_brightness_changed)
        slider_layout.addWidget(self.brightness_slider)
        self.brightness_value_label = QLabel("100%")
        self.brightness_value_label.setObjectName("label_brightness_value")
        slider_layout.addWidget(self.brightness_value_label)
        layout.addLayout(slider_layout)

        group.setLayout(layout)
        self.tab_simple_layout.addWidget(group)

    def _create_control_section(self) -> None:
        """Creates hardware control section."""
        group = QWidget()
        group.setObjectName("card")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 16)

        title = QLabel("Device Controls")
        title.setObjectName("label_section_title")
        layout.addWidget(title)

        btn_layout = QHBoxLayout()
        self.btn_screen_power = QPushButton("⏻  Screen ON / OFF")
        self.btn_screen_power.setObjectName("btn_ghost")
        self.btn_screen_power.clicked.connect(self._on_toggle_screen)
        btn_layout.addWidget(self.btn_screen_power)

        self.btn_reboot = QPushButton("↻  Reboot")
        self.btn_reboot.setObjectName("btn_reboot")
        self.btn_reboot.clicked.connect(self._on_reboot)
        btn_layout.addWidget(self.btn_reboot)

        self.btn_clear_memory = QPushButton("⌫  Clear Storage")
        self.btn_clear_memory.setObjectName("btn_ghost")
        self.btn_clear_memory.clicked.connect(self._on_clear_memory)
        btn_layout.addWidget(self.btn_clear_memory)

        self.btn_device_media = QPushButton("▤  Device Media")
        self.btn_device_media.setObjectName("btn_ghost")
        self.btn_device_media.clicked.connect(self._on_show_device_media)
        btn_layout.addWidget(self.btn_device_media)

        layout.addLayout(btn_layout)
        group.setLayout(layout)
        self.tab_simple_layout.addWidget(group)

    def _create_log_section(self) -> None:
        """Creates collapsible event log panel."""
        self.log_container = QWidget()
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(4)

        self.btn_toggle_logs = QPushButton("▶  Show Event Log")
        self.btn_toggle_logs.setObjectName("btn_toggle_logs")
        self.btn_toggle_logs.setCheckable(True)
        self.btn_toggle_logs.setChecked(False)
        self.btn_toggle_logs.clicked.connect(self._toggle_logs)

        self.log_panel = QTextEdit()
        self.log_panel.setObjectName("log_panel")
        self.log_panel.setReadOnly(True)
        self.log_panel.setVisible(False)
        self.log_panel.setMaximumHeight(120)

        log_layout.addWidget(self.btn_toggle_logs)
        log_layout.addWidget(self.log_panel)

        self.main_container.addWidget(self.log_container)

    def _toggle_logs(self, checked: bool) -> None:
        """Expands or collapses the event log panel."""
        self.log_panel.setVisible(checked)
        if checked:
            self.btn_toggle_logs.setText("▼  Hide Event Log")
        else:
            self.btn_toggle_logs.setText("▶  Show Event Log")

    # ================================================================
    # BACKGROUND DEVICE PING
    # ================================================================

    def _start_ping_worker(self) -> None:
        self.ping_worker = PingWorker(self.client, interval_ms=PING_INTERVAL_MS)
        self.ping_worker.status_changed.connect(self._on_status_changed)
        self.ping_worker.grid_updated.connect(self._on_grid_updated)
        self.ping_worker.brightness_received.connect(self._on_initial_brightness_received)
        self.ping_worker.start()

    def _on_initial_brightness_received(self, value: int) -> None:
        self.brightness_slider.blockSignals(True)
        self.brightness_slider.setValue(value)
        self.brightness_value_label.setText(f"{value}%")
        self.brightness_slider.blockSignals(False)
        self.log(f"Current brightness synchronized with device: {value}%")

    def _on_grid_updated(self) -> None:
        self.log("Screen grid updated based on device telemetry")
        self.scene_editor.refresh_grid()

    def _on_status_changed(self, is_online: bool) -> None:
        if is_online:
            self.status_indicator.setText("●  Online")
            self.status_indicator.setObjectName("label_status_online")
        else:
            self.status_indicator.setText("●  Offline")
            self.status_indicator.setObjectName("label_status_offline")

        self.status_indicator.style().unpolish(self.status_indicator)
        self.status_indicator.style().polish(self.status_indicator)

    def _on_hardware_settings(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Hardware & Connection Settings")
        dialog.setMinimumWidth(550)
        dialog.resize(600, 650)

        main_layout = QVBoxLayout(dialog)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(0, 0, 0, 8)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(16)
        scroll_layout.setContentsMargins(16, 16, 16, 16)

        # Group 0: Connection Mode
        group_net = QGroupBox("LED Player Connection Type")
        layout_net = QVBoxLayout(group_net)
        layout_net.setContentsMargins(16, 20, 16, 16)
        layout_net.setSpacing(12)

        radio_layout = QHBoxLayout()
        rb_lan = QRadioButton("LAN (Ethernet Cable)")
        rb_wifi = QRadioButton("Wi-Fi (KU6 Access Point)")

        if CONNECTION_MODE == "WIFI":
            rb_wifi.setChecked(True)
        else:
            rb_lan.setChecked(True)

        radio_layout.addWidget(rb_lan)
        radio_layout.addWidget(rb_wifi)
        layout_net.addLayout(radio_layout)

        btn_connect_wifi = QPushButton("Connect to Player Wi-Fi (Automatic)")
        btn_connect_wifi.setObjectName("btn_ghost")

        def _connect_to_wifi():
            import subprocess
            import tempfile

            ssid = "KU6-26050021"
            password = "26050021"

            profile_xml = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID>
            <name>{ssid}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{password}</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>"""
            try:
                temp_dir = tempfile.gettempdir()
                xml_path = os.path.join(temp_dir, f"{ssid}.xml")
                with open(xml_path, "w", encoding="utf-8") as f:
                    f.write(profile_xml)

                subprocess.run(
                    ["netsh", "wlan", "add", "profile", f"filename={xml_path}"],
                    check=True,
                    capture_output=True,
                )
                subprocess.run(
                    ["netsh", "wlan", "connect", f"name={ssid}"],
                    check=True,
                    capture_output=True,
                )

                QMessageBox.information(
                    dialog,
                    "Connection",
                    f"Command sent to connect to Wi-Fi: {ssid}.\nPlease wait a few seconds while connection is established.",
                )
                rb_wifi.setChecked(True)
            except Exception as e:
                QMessageBox.warning(
                    dialog,
                    "Error",
                    f"Failed to automatically connect to Wi-Fi. Administrator privileges may be required.\n\nYou can manually connect via the OS Wi-Fi menu.\n\nCode: {e}",
                )

        btn_connect_wifi.clicked.connect(_connect_to_wifi)
        layout_net.addWidget(btn_connect_wifi)

        scroll_layout.addWidget(group_net)

        # Group 1: LED Panel Grid
        group_grid = QGroupBox("LED Panel Grid")
        layout_grid = QFormLayout(group_grid)
        layout_grid.setContentsMargins(16, 20, 16, 16)

        spin_w = QSpinBox()
        spin_w.setRange(10, 2000)
        spin_w.setValue(PANEL_WIDTH)

        spin_h = QSpinBox()
        spin_h.setRange(10, 2000)
        spin_h.setValue(PANEL_HEIGHT)

        spin_cols = QSpinBox()
        spin_cols.setRange(1, 100)
        spin_cols.setValue(SCREEN_COLS)

        spin_rows = QSpinBox()
        spin_rows.setRange(1, 100)
        spin_rows.setValue(SCREEN_ROWS)

        chk_auto = QCheckBox()
        chk_auto.setChecked(AUTO_GRID)

        layout_grid.addRow("Panel Width (px):", spin_w)
        layout_grid.addRow("Panel Height (px):", spin_h)
        layout_grid.addRow("Columns (X):", spin_cols)
        layout_grid.addRow("Rows (Y):", spin_rows)
        layout_grid.addRow("Auto-detect grid from canvas:", chk_auto)

        scroll_layout.addWidget(group_grid)

        # Group 2: Video Optimization
        group_opt = QGroupBox("Video Optimization (FFmpeg)")
        layout_opt = QVBoxLayout(group_opt)
        layout_opt.setContentsMargins(16, 20, 16, 16)
        layout_opt.setSpacing(12)

        chk_auto_opt = QCheckBox("Automatically optimize video in 'Simple Mode'")
        chk_auto_opt.setChecked(AUTO_OPTIMIZE_VIDEO)
        lbl_auto_opt = QLabel("Scales video to canvas dimensions prior to upload to eliminate playback lag.")
        lbl_auto_opt.setWordWrap(True)
        lbl_auto_opt.setStyleSheet("color: gray; font-size: 11px; margin-left: 24px;")

        chk_crush = QCheckBox("Suppress digital noise on dark backgrounds (Crush Blacks)")
        chk_crush.setChecked(CRUSH_BLACKS)
        lbl_crush = QLabel("Clamps near-black pixels to pure (0,0,0) to eliminate colored pixel artifacts.")
        lbl_crush.setWordWrap(True)
        lbl_crush.setStyleSheet("color: gray; font-size: 11px; margin-left: 24px;")

        chk_limit = QCheckBox("Optimize bitrate and smoothness (GOP 30, Max 4M)")
        chk_limit.setChecked(LIMIT_BITRATE)
        lbl_limit = QLabel("Reduces controller CPU load. Enable if high-framerate playback stutters.")
        lbl_limit.setWordWrap(True)
        lbl_limit.setStyleSheet("color: gray; font-size: 11px; margin-left: 24px;")

        layout_opt.addWidget(chk_auto_opt)
        layout_opt.addWidget(lbl_auto_opt)
        layout_opt.addWidget(chk_crush)
        layout_opt.addWidget(lbl_crush)
        layout_opt.addWidget(chk_limit)
        layout_opt.addWidget(lbl_limit)

        scroll_layout.addWidget(group_opt)

        # Group 3: Entertainment / Screensavers
        group_fun = QGroupBox("Entertainment / Screensavers")
        layout_fun = QVBoxLayout(group_fun)
        layout_fun.setContentsMargins(16, 20, 16, 16)

        btn_ping_pong = QPushButton("🏓 Launch Ping-Pong Screensaver")
        btn_ping_pong.setObjectName("btn_secondary")
        btn_ping_pong.setMinimumHeight(32)

        ping_pong_progress = QProgressBar()
        ping_pong_progress.setTextVisible(False)
        ping_pong_progress.setFixedHeight(4)
        ping_pong_progress.setVisible(False)

        def _run_ping_pong():
            btn_ping_pong.setEnabled(False)
            btn_ping_pong.setText("Generating frames...")
            ping_pong_progress.setVisible(True)
            ping_pong_progress.setValue(0)

            self.ping_pong_worker = PingPongWorker(self.client)

            def _on_prog(p):
                ping_pong_progress.setValue(p)
                if p > 50:
                    btn_ping_pong.setText("Assembling video (FFmpeg)...")
                if p > 80:
                    btn_ping_pong.setText("Deploying to LED screen...")

            def _on_finish(success, msg):
                btn_ping_pong.setEnabled(True)
                btn_ping_pong.setText("🏓 Launch Ping-Pong Screensaver")
                ping_pong_progress.setVisible(False)
                if success:
                    self.log("Ping-Pong screensaver launched successfully!")
                else:
                    self.log(f"Ping-Pong error: {msg}")
                    QMessageBox.warning(dialog, "Error", msg)

            self.ping_pong_worker.progress.connect(_on_prog)
            self.ping_pong_worker.finished.connect(_on_finish)
            self.ping_pong_worker.start()

        btn_ping_pong.clicked.connect(_run_ping_pong)

        layout_fun.addWidget(btn_ping_pong)
        layout_fun.addWidget(ping_pong_progress)

        scroll_layout.addWidget(group_fun)

        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        # Bottom Save Button
        btn_save = QPushButton("Save Settings")
        btn_save.setObjectName("btn_primary")
        btn_save.setMinimumHeight(40)
        btn_save.clicked.connect(dialog.accept)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(16, 0, 16, 8)
        btn_layout.addWidget(btn_save)
        main_layout.addLayout(btn_layout)

        if dialog.exec():
            new_mode = "WIFI" if rb_wifi.isChecked() else "LAN"
            save_hardware_config(
                spin_w.value(),
                spin_h.value(),
                spin_cols.value(),
                spin_rows.value(),
                chk_auto.isChecked(),
                auto_optimize=chk_auto_opt.isChecked(),
                crush_blacks=chk_crush.isChecked(),
                limit_bitrate=chk_limit.isChecked(),
                connection_mode=new_mode,
            )
            self.log(f"Settings saved: {spin_cols.value()}x{spin_rows.value()} (Mode: {new_mode})")

            base_url, reboot_url = get_current_urls()
            self.client.update_urls(base_url, reboot_url)

            screen_config.update_from_device_info(screen_config.total_width, screen_config.total_height)
            self.scene_editor.refresh_grid()

    # ================================================================
    # PLAYLIST EVENT HANDLERS
    # ================================================================

    def _refresh_programs_list(self) -> None:
        self.list_programs.blockSignals(True)
        self.list_programs.clear()
        for p in self.playlists_manager.get_all_programs():
            self.list_programs.addItem(p["name"])
        self.list_programs.blockSignals(False)

        if self.list_programs.count() > 0:
            self.list_programs.setCurrentRow(0)
            self._on_program_selected()

    def _get_selected_program_id(self) -> str | None:
        row = self.list_programs.currentRow()
        if row < 0:
            return None
        return self.playlists_manager.get_all_programs()[row]["id"]

    def _save_current_program_files(self) -> None:
        if self.current_program_id:
            files = [
                self.media_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.media_list.count())
            ]
            self.playlists_manager.set_program_files(self.current_program_id, files)

    def _on_program_selected(self) -> None:
        prog_id = self._get_selected_program_id()
        if not prog_id:
            return

        self._save_current_program_files()
        self.current_program_id = prog_id

        self.media_list.clear()
        files = self.playlists_manager.get_program_files(prog_id)
        for f in files:
            path = Path(f)
            ext = path.suffix.lower()
            icon_str = "🎬" if ext in VIDEO_EXTENSIONS else ""
            item = QListWidgetItem(f"{icon_str}  {path.name}".strip())

            pixmap = self._get_media_thumbnail(str(path), ext)
            if pixmap:
                item.setIcon(QIcon(pixmap))

            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            self.media_list.addItem(item)

        self.log(f"Selected program: {self.list_programs.currentItem().text()}")

    def _on_add_program(self) -> None:
        name, ok = QInputDialog.getText(self, "New Program", "Enter program name:")
        if ok and name.strip():
            self.playlists_manager.add_program(name.strip())
            self._refresh_programs_list()
            self.list_programs.setCurrentRow(self.list_programs.count() - 1)

    def _on_rename_program(self) -> None:
        prog_id = self._get_selected_program_id()
        if not prog_id:
            return
        current_name = self.list_programs.currentItem().text()
        new_name, ok = QInputDialog.getText(self, "Rename Program", "New name:", text=current_name)
        if ok and new_name.strip():
            self.playlists_manager.rename_program(prog_id, new_name.strip())
            self._refresh_programs_list()

    def _on_delete_program(self) -> None:
        prog_id = self._get_selected_program_id()
        if not prog_id:
            return
        if len(self.playlists_manager.get_all_programs()) <= 1:
            QMessageBox.warning(self, "Error", "Cannot delete the last remaining program.")
            return

        if self.current_program_id == prog_id:
            self.current_program_id = None
        self.playlists_manager.delete_program(prog_id)
        self._refresh_programs_list()

    # ================================================================
    # MEDIA EVENT HANDLERS
    # ================================================================

    def _get_media_thumbnail(self, file_path: str, ext: str) -> QPixmap | None:
        """Generates a thumbnail for a media file (image, video, or GIF)."""
        pixmap = None
        if ext in IMAGE_THUMBNAIL_EXTENSIONS:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                return None
        elif ext in VIDEO_THUMBNAIL_EXTENSIONS:
            thumb_bytes = get_video_thumbnail_bytes(file_path, 64, 64)
            if thumb_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(thumb_bytes)
                if pixmap.isNull():
                    return None
            else:
                return None
        else:
            return None

        return pixmap.scaled(
            64, 64,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def open_file_dialog(self) -> None:
        all_exts = " ".join(f"*{ext}" for ext in sorted(ALLOWED_EXTENSIONS))
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", f"All Media ({all_exts})")
        if files:
            self.add_media_files(files)

    def add_media_files(self, file_paths: list[str]) -> None:
        existing_paths = {
            self.media_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.media_list.count())
        }
        added_count = 0
        for p in file_paths:
            path = Path(p)
            if str(path) not in existing_paths:
                file_size = os.path.getsize(path)
                size_str = self._format_size(file_size)
                ext = path.suffix.lower()

                if ext in VIDEO_EXTENSIONS:
                    icon_str = "🎬"
                    type_str = "Video"
                else:
                    icon_str = ""
                    type_str = "Image"

                item_text = f"{icon_str}  {path.name}    ({size_str}, {type_str})".strip()
                item = QListWidgetItem(item_text)

                pixmap = self._get_media_thumbnail(str(path), ext)
                if pixmap:
                    item.setIcon(QIcon(pixmap))
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                item.setToolTip(str(path))
                self.media_list.addItem(item)

                self.log(f"+ Added: {path.name} ({size_str})")
                existing_paths.add(str(path))
                added_count += 1

        if added_count > 0:
            self._save_current_program_files()

    def _on_remove_media_item(self, item: QListWidgetItem) -> None:
        """Removes an item from local list on double click."""
        row = self.media_list.row(item)
        removed = self.media_list.takeItem(row)
        if removed:
            path = Path(removed.data(Qt.ItemDataRole.UserRole))
            self.log(f"- Removed from list: {path.name}")
            self._save_current_program_files()

    def _on_clear_media_list(self) -> None:
        """Clears all items from the media list."""
        self.media_list.clear()
        self.log("  Media list cleared")
        self._save_current_program_files()

    def _on_play_media(self) -> None:
        """
        Executes two-stage upload and program playback.

        Collects paths from list and forwards to UploadMediaWorker
        executing: MD5 -> checkUpload -> uploadMedia -> uploadThirdProgram
        in an asynchronous background thread.
        """
        file_paths = []
        for i in range(self.media_list.count()):
            item = self.media_list.item(i)
            file_paths.append(item.data(Qt.ItemDataRole.UserRole))

        if not file_paths:
            self.log("⚠ Add media files to the library first")
            return

        self.btn_play_media.setEnabled(False)
        self.btn_play_media.setText("⏳  Uploading...")
        self.upload_progress.setVisible(True)
        self.upload_progress.setValue(0)
        self.btn_cancel_upload.setVisible(True)
        self.btn_cancel_upload.setEnabled(True)
        self.btn_cancel_upload.setText("Cancel")

        worker = UploadMediaWorker(
            client=self.client,
            file_paths=file_paths,
            image_duration_sec=self.spin_image_duration.value(),
        )
        worker.progress.connect(self.upload_progress.setValue)
        worker.finished.connect(self._on_media_upload_finished)
        worker.finished.connect(lambda *args: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

        self.log(f"→ Uploading {len(file_paths)} files to device...")

    def _on_cancel_upload(self) -> None:
        """Cancels current upload worker."""
        self.btn_cancel_upload.setEnabled(False)
        self.btn_cancel_upload.setText("Cancelling...")
        self.log("⚠ Aborting upload...")

        for w in self._active_workers:
            if isinstance(w, UploadMediaWorker):
                w._is_aborted = True

        self.client.abort_all_requests()

    def _on_media_upload_finished(self, success: bool, message: str) -> None:
        """Handles upload completion signal."""
        self.btn_play_media.setEnabled(True)
        self.btn_play_media.setText("▶  Play on LED")
        self.btn_cancel_upload.setVisible(False)

        if success:
            self.upload_progress.setValue(100)
            self.log(f"✓ {message}")
            QTimer.singleShot(2000, lambda: self.upload_progress.setVisible(False))
        else:
            self.upload_progress.setVisible(False)
            self.log(f"✗ {message}")

    # ================================================================
    # BRIGHTNESS EVENT HANDLERS
    # ================================================================

    def _on_brightness_changed(self, value: int) -> None:
        """
        Handles brightness slider adjustments.
        Uses debounce timer to prevent request flooding.
        """
        self._pending_brightness = value
        self.brightness_value_label.setText(f"{value}%")
        self._brightness_timer.start()

    def _send_brightness(self) -> None:
        """Dispatches debounced brightness level to device."""
        value = self._pending_brightness

        worker = BrightnessWorker(client=self.client, value=value)
        worker.finished.connect(self._on_brightness_sent)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_brightness_sent(self, success: bool, message: str) -> None:
        """Handles brightness response signal."""
        if success:
            self.log(f"☀ {message}")
        else:
            self.log(f"✗ {message}")

    # ================================================================
    # DEVICE CONTROL EVENT HANDLERS
    # ================================================================

    def _on_toggle_screen(self) -> None:
        """Toggles display power state."""
        new_state = not self._screen_on
        self.btn_screen_power.setEnabled(False)

        worker = ScreenPowerWorker(client=self.client, power_on=new_state)
        worker.finished.connect(lambda ok, msg: self._on_screen_toggled(ok, msg, new_state))
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_screen_toggled(self, success: bool, message: str, new_state: bool) -> None:
        """Handles screen toggle response signal."""
        self.btn_screen_power.setEnabled(True)
        if success:
            self._screen_on = new_state
            self.log(f"⏻ {message}")
        else:
            self.log(f"✗ {message}")

    def _on_reboot(self) -> None:
        """Reboots device upon user confirmation."""
        reply = QMessageBox.question(
            self,
            "Confirmation",
            "Are you sure you want to reboot the media player?\nActive playback will be interrupted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.btn_reboot.setEnabled(False)

        worker = RebootWorker(client=self.client)
        worker.finished.connect(self._on_reboot_finished)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_reboot_finished(self, success: bool, message: str) -> None:
        """Handles reboot response signal."""
        self.btn_reboot.setEnabled(True)
        if success:
            self.log(f"↻ {message}")
        else:
            self.log(f"✗ {message}")

    def _on_clear_memory(self) -> None:
        """Prompts and initiates deletion of all player files."""
        reply = QMessageBox.question(
            self,
            "Clear Storage",
            "Are you sure you want to delete ALL files from the player?\nThis frees device memory, but files will be re-uploaded on next playback.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.btn_clear_memory.setEnabled(False)
        self.btn_clear_memory.setText("⏳  Clearing...")

        worker = ClearMemoryWorker(self.client)
        worker.progress.connect(lambda p: self.log(f"  Deleting files: {p}%"))
        worker.finished.connect(self._on_clear_memory_finished)
        worker.finished.connect(lambda *args: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

        self.log("Started clearing player memory...")

    def _on_clear_memory_finished(self, success: bool, message: str) -> None:
        """Handles memory clearing response signal."""
        self.btn_clear_memory.setEnabled(True)
        self.btn_clear_memory.setText("⌫  Clear Storage")

        if success:
            self.log(f"✓ {message}")
            QMessageBox.information(self, "Success", message)
        else:
            self.log(f"✗ {message}")
            QMessageBox.critical(self, "Error", message)

    def _on_show_device_media(self) -> None:
        """Opens the device media file manager dialog."""
        dialog = DeviceMediaDialog(self, self.client, self.playlists_manager)
        dialog.exec()

    # ================================================================
    # UTILITIES
    # ================================================================

    def log(self, message: str) -> None:
        """
        Appends a timestamped log entry to the UI log panel.

        Args:
            message: Informational text string to display.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_panel.append(f"[{timestamp}]  {message}")
        scrollbar = self.log_panel.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Formats file size into human-readable representation."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def _cleanup_worker(self, worker) -> None:
        """Removes finished worker thread from active list."""
        try:
            self._active_workers.remove(worker)
        except ValueError:
            pass

    # ================================================================
    # LIFECYCLE
    # ================================================================

    def closeEvent(self, event) -> None:
        """Gracefully tears down network connections and worker threads upon application exit."""
        if hasattr(self, "tab_dynamic_video"):
            self.tab_dynamic_video.cleanup()

        self.client.abort_all_requests()

        if hasattr(self, "ping_worker"):
            self.ping_worker.stop()

        for w in self._active_workers:
            if hasattr(w, "stop"):
                w.stop()
            elif hasattr(w, "_is_aborted"):
                w._is_aborted = True
                w.wait(1000)
            else:
                w.wait(1000)

        if hasattr(self, "scene_editor") and hasattr(self.scene_editor, "worker") and self.scene_editor.worker:
            try:
                if self.scene_editor.worker.isRunning():
                    self.scene_editor.worker.wait(3000)
            except RuntimeError:
                pass

        event.accept()

    # ================================================================
    # SCENE EDITOR & FFMPEG INTEGRATION
    # ================================================================

    def _on_render_completed(self, file_path: str) -> None:
        """Fires upon successful completion of scene rendering via SceneEditor."""
        name = f"Scene {datetime.now().strftime('%H:%M:%S')}"

        prog = self.playlists_manager.add_program(name)
        self.playlists_manager.set_program_files(prog["id"], [file_path])

        self.log(f"✦ Created new playlist '{name}' with assembled scene")
        self._refresh_programs_list()

        items = self.list_programs.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self.list_programs.setCurrentItem(items[0])

        self._on_play_media()
