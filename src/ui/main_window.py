# -*- coding: utf-8 -*-
"""
main_window.py — Главное окно приложения Kystar KD6 Control Panel.

Этот модуль содержит ТОЛЬКО UI-логику PyQt6:
- Создание и компоновку виджетов
- Обработку событий пользователя (клики, Drag-and-Drop, слайдер)
- Запуск рабочих потоков для сетевых операций
- Обновление UI по сигналам от воркеров

Вся сетевая логика делегирована модулям kystar_client.py и workers.py.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl, QSize
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QInputDialog,
    QDialog,
    QFormLayout,
    QTabWidget,
    QSizePolicy,
    QCheckBox,
)

from src.core.config import (
    ALLOWED_EXTENSIONS,
    BRIGHTNESS_DEBOUNCE_MS,
    DEVICE_IP,
    IMAGE_EXTENSIONS,
    PING_INTERVAL_MS,
    VIDEO_EXTENSIONS,
    screen_config,
    save_hardware_config,
    PANEL_WIDTH,
    PANEL_HEIGHT,
)
from src.core.kystar_client import KystarClient
from src.core.playlists_manager import PlaylistsManager
from src.core.media_utils import (
    get_video_thumbnail_bytes,
    IMAGE_THUMBNAIL_EXTENSIONS,
    VIDEO_THUMBNAIL_EXTENSIONS,
)
from src.ui.scene_editor import SceneEditor
from src.ui.device_media_dialog import DeviceMediaDialog
from src.ui.dynamic_video_tab import DynamicVideoTab
from src.ui.styles import DROP_ZONE_HOVER_STYLE, DROP_ZONE_STYLE
from src.ui.workers import (
    BrightnessWorker,
    PingWorker,
    RebootWorker,
    ScreenPowerWorker,
    UploadMediaWorker,
)
logger = logging.getLogger(__name__)


class DropZoneLabel(QLabel):
    """
    Виджет-зона для Drag-and-Drop файлов.

    Принимает перетаскиваемые файлы с расширениями из ALLOWED_EXTENSIONS.
    При наведении файлов подсвечивает зону неоновой рамкой.
    """

    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        self.main_window = parent
        self.setObjectName("drop_zone")
        self.setText("📁  Перетащите медиафайлы сюда\nили нажмите для выбора")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(DROP_ZONE_STYLE)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Подсвечиваем зону при наведении файлов."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(DROP_ZONE_HOVER_STYLE)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        """Снимаем подсветку при уходе курсора."""
        self.setStyleSheet(DROP_ZONE_STYLE)

    def dropEvent(self, event: QDropEvent) -> None:
        """Обрабатываем сброшенные файлы."""
        self.setStyleSheet(DROP_ZONE_STYLE)
        urls = event.mimeData().urls()
        file_paths: list[str] = []
        for url in urls:
            path = url.toLocalFile()
            ext = Path(path).suffix.lower()
            if ext in ALLOWED_EXTENSIONS:
                file_paths.append(path)
            else:
                self.main_window.log(f"⚠ Пропущен неподдерживаемый файл: {Path(path).name}")
        if file_paths:
            self.main_window.add_media_files(file_paths)
        event.acceptProposedAction()

    def mousePressEvent(self, event) -> None:
        """Открываем диалог выбора файлов при клике."""
        self.main_window.open_file_dialog()


class MainWindow(QMainWindow):
    """
    Главное окно приложения управления LED-экраном Kystar KD6.
    """

    def __init__(self) -> None:
        super().__init__()

        # Инициализация API-клиента (без сетевых вызовов в конструкторе)
        self.client = KystarClient()

        # Список рабочих потоков для предотвращения сборки мусора
        self._active_workers: list = []

        # База данных плейлистов
        self.playlists_manager = PlaylistsManager()
        self.current_program_id = None

        # Таймер debounce для слайдера яркости
        self._brightness_timer = QTimer()
        self._brightness_timer.setSingleShot(True)
        self._brightness_timer.setInterval(BRIGHTNESS_DEBOUNCE_MS)
        self._brightness_timer.timeout.connect(self._send_brightness)

        # Последнее значение яркости для debounce
        self._pending_brightness: int = 100

        # Текущее состояние экрана
        self._screen_on: bool = True

        self._setup_ui()
        self._start_ping_worker()

    # ================================================================
    # НАСТРОЙКА ИНТЕРФЕЙСА
    # ================================================================

    def _setup_ui(self) -> None:
        """Создаёт и компонует все UI-элементы."""
        self.setWindowTitle("Kystar KD6 — LED Control Panel")
        
        # Установка иконки приложения
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.setMinimumSize(900, 700)
        self.resize(1000, 900)

        # Центральный виджет
        central_widget = QWidget()
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(20, 12, 20, 20)
        root_layout.setSpacing(20)

        self.left_layout = QVBoxLayout()
        root_layout.addLayout(self.left_layout)

        self.main_container = QVBoxLayout()
        self.main_container.setSpacing(12)
        root_layout.addLayout(self.main_container, stretch=1)

        # --- Секция плейлистов (слева) ---
        self._create_playlists_section()

        # Создаем табы
        self.tabs = QTabWidget()
        self.main_container.addWidget(self.tabs)

        self.tab_simple = QWidget()
        self.tab_simple_layout = QVBoxLayout(self.tab_simple)
        self.tabs.addTab(self.tab_simple, "Простой режим (Плейлисты)")

        self.tab_scene = QWidget()
        self.tab_scene_layout = QVBoxLayout(self.tab_scene)
        self.tabs.addTab(self.tab_scene, "Визуальный редактор зон (Multi-layer)")

        self.tab_dynamic_video = DynamicVideoTab(self)
        self.tabs.addTab(self.tab_dynamic_video, "Динамическое видео")

        # --- Заголовок ---
        self._create_header()

        # --- Секция медиа ---
        self._create_media_section()

        # --- Секция яркости ---
        self._create_brightness_section()

        # --- Секция управления ---
        self._create_control_section()

        # --- Добавляем Редактор Сцен ---
        self.scene_editor = SceneEditor(self)
        self.scene_editor.render_completed.connect(self._on_render_completed)
        self.tab_scene_layout.addWidget(self.scene_editor)

        # --- Лог событий ---
        self._create_log_section()

        self.setCentralWidget(central_widget)

        # Приветственное сообщение
        self.log("✦ Kystar KD6 Control Panel запущен")
        self.log(f"  Устройство: {DEVICE_IP}")

        # Загружаем плейлисты только после создания всех виджетов
        self._refresh_programs_list()

    def _create_playlists_section(self) -> None:
        """Создаёт секцию управления плейлистами слева."""
        group = QWidget()
        group.setObjectName("card")
        group.setMaximumWidth(280)
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        
        title = QLabel("Программы (Плейлисты)")
        title.setObjectName("label_section_title")
        layout.addWidget(title)

        self.list_programs = QListWidget()
        self.list_programs.itemSelectionChanged.connect(self._on_program_selected)
        layout.addWidget(self.list_programs)

        btn_row = QHBoxLayout()
        self.btn_add_program = QPushButton("Создать")
        self.btn_add_program.setObjectName("btn_ghost")
        self.btn_add_program.clicked.connect(self._on_add_program)
        btn_row.addWidget(self.btn_add_program)

        self.btn_rename_program = QPushButton("Имя")
        self.btn_rename_program.setObjectName("btn_ghost")
        self.btn_rename_program.clicked.connect(self._on_rename_program)
        btn_row.addWidget(self.btn_rename_program)

        self.btn_delete_program = QPushButton("Удалить")
        self.btn_delete_program.setObjectName("btn_delete")
        self.btn_delete_program.clicked.connect(self._on_delete_program)
        btn_row.addWidget(self.btn_delete_program)

        layout.addLayout(btn_row)
        group.setLayout(layout)
        
        # Разрешаем группе растягиваться
        group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.left_layout.addWidget(group)

        self.btn_hardware_settings = QPushButton("Настройки оборудования")
        self.btn_hardware_settings.setObjectName("btn_ghost")
        self.btn_hardware_settings.clicked.connect(self._on_hardware_settings)
        self.left_layout.addWidget(self.btn_hardware_settings)

    def _create_header(self) -> None:
        """Создаёт заголовок с названием и индикатором статуса."""
        header_layout = QHBoxLayout()
        title_label = QLabel("KYSTAR KD6 CONTROL")
        title_label.setObjectName("label_title")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        self.status_indicator = QLabel("●  Проверка...")
        self.status_indicator.setObjectName("label_status_offline")
        header_layout.addWidget(self.status_indicator)
        self.tab_simple_layout.addLayout(header_layout)

    def _create_media_section(self) -> None:
        """Создаёт секцию медиабиблиотеки с Drag-and-Drop."""
        group = QWidget()
        group.setObjectName("card")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        
        title = QLabel("Медиабиблиотека")
        title.setObjectName("label_section_title")
        layout.addWidget(title)
        
        self.drop_zone = DropZoneLabel(self)
        layout.addWidget(self.drop_zone)
        self.media_list = QListWidget()
        self.media_list.setIconSize(QSize(64, 64))
        self.media_list.itemDoubleClicked.connect(self._on_remove_media_item)
        layout.addWidget(self.media_list)
        
        btn_row = QHBoxLayout()
        self.btn_add_files = QPushButton("Добавить файлы")
        self.btn_add_files.setObjectName("btn_ghost")
        self.btn_add_files.clicked.connect(self.open_file_dialog)
        btn_row.addWidget(self.btn_add_files)
        
        self.btn_clear_list = QPushButton("Очистить список")
        self.btn_clear_list.setObjectName("btn_ghost")
        self.btn_clear_list.clicked.connect(self._on_clear_media_list)
        btn_row.addWidget(self.btn_clear_list)
        layout.addLayout(btn_row)

        play_row = QHBoxLayout()
        self.btn_play_media = QPushButton("Воспроизвести на LED")
        self.btn_play_media.setObjectName("btn_primary")
        self.btn_play_media.clicked.connect(self._on_play_media)
        play_row.addWidget(self.btn_play_media, stretch=2)

        play_row.addWidget(QLabel("Длительность фото:"))
        self.spin_image_duration = QSpinBox()
        self.spin_image_duration.setRange(1, 3600)
        self.spin_image_duration.setValue(5)
        self.spin_image_duration.setSuffix(" с")
        play_row.addWidget(self.spin_image_duration, stretch=1)
        layout.addLayout(play_row)

        progress_layout = QHBoxLayout()
        self.upload_progress = QProgressBar()
        self.upload_progress.setVisible(False)
        progress_layout.addWidget(self.upload_progress)
        
        self.btn_cancel_upload = QPushButton("Отмена")
        self.btn_cancel_upload.setObjectName("btn_ghost")
        self.btn_cancel_upload.setVisible(False)
        self.btn_cancel_upload.clicked.connect(self._on_cancel_upload)
        progress_layout.addWidget(self.btn_cancel_upload)
        
        layout.addLayout(progress_layout)
        group.setLayout(layout)
        self.tab_simple_layout.addWidget(group)

    def _create_brightness_section(self) -> None:
        """Создаёт секцию управления яркостью."""
        group = QWidget()
        group.setObjectName("card")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 16)
        
        title = QLabel("Яркость экрана")
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
        """Создаёт секцию управления устройством."""
        group = QWidget()
        group.setObjectName("card")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 16)
        
        title = QLabel("Управление устройством")
        title.setObjectName("label_section_title")
        layout.addWidget(title)
        
        btn_layout = QHBoxLayout()
        self.btn_screen_power = QPushButton("⏻  Экран вкл / выкл")
        self.btn_screen_power.setObjectName("btn_ghost")
        self.btn_screen_power.clicked.connect(self._on_toggle_screen)
        btn_layout.addWidget(self.btn_screen_power)
        
        self.btn_reboot = QPushButton("↻  Перезагрузка")
        self.btn_reboot.setObjectName("btn_reboot")
        self.btn_reboot.clicked.connect(self._on_reboot)
        btn_layout.addWidget(self.btn_reboot)
        
        self.btn_clear_memory = QPushButton("⌫  Очистить память")
        self.btn_clear_memory.setObjectName("btn_ghost")
        self.btn_clear_memory.clicked.connect(self._on_clear_memory)
        btn_layout.addWidget(self.btn_clear_memory)
        
        self.btn_device_media = QPushButton("▤  Медиа на плеере")
        self.btn_device_media.setObjectName("btn_ghost")
        self.btn_device_media.clicked.connect(self._on_show_device_media)
        btn_layout.addWidget(self.btn_device_media)
        
        layout.addLayout(btn_layout)
        group.setLayout(layout)
        self.tab_simple_layout.addWidget(group)

    def _create_log_section(self) -> None:
        """Создаёт сворачиваемую панель лога событий."""
        self.log_container = QWidget()
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(4)
        
        self.btn_toggle_logs = QPushButton("▶  Показать лог событий")
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
        """Сворачивает или разворачивает лог событий."""
        self.log_panel.setVisible(checked)
        if checked:
            self.btn_toggle_logs.setText("▼  Скрыть лог событий")
        else:
            self.btn_toggle_logs.setText("▶  Показать лог событий")

    # ================================================================
    # ФОНОВЫЙ ПИНГ УСТРОЙСТВА
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
        self.log(f"Текущая яркость синхронизирована с устройством: {value}%")

    def _on_grid_updated(self) -> None:
        self.log("Сетка экранов обновлена на основе данных от устройства")
        self.scene_editor.refresh_grid()

    def _on_status_changed(self, is_online: bool) -> None:
        if is_online:
            self.status_indicator.setText("●  Онлайн")
            self.status_indicator.setObjectName("label_status_online")
        else:
            self.status_indicator.setText("●  Оффлайн")
            self.status_indicator.setObjectName("label_status_offline")
            
        self.status_indicator.style().unpolish(self.status_indicator)
        self.status_indicator.style().polish(self.status_indicator)

    def _on_hardware_settings(self) -> None:
        from src.core.config import SCREEN_COLS, SCREEN_ROWS, AUTO_GRID, AUTO_OPTIMIZE_VIDEO, CRUSH_BLACKS, LIMIT_BITRATE, CONNECTION_MODE, get_current_urls
        dialog = QDialog(self)
        dialog.setWindowTitle("Настройки оборудования и подключения")
        dialog.setMinimumWidth(550)
        dialog.resize(600, 650) # Устанавливаем высоту по умолчанию, но она может сжиматься
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(0, 0, 0, 8)
        
        from PyQt6.QtWidgets import QScrollArea, QWidget, QFrame
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(16)
        scroll_layout.setContentsMargins(16, 16, 16, 16)
        
        # Группа 0: Подключение к плееру
        group_net = QGroupBox("Тип подключения к LED-плееру")
        layout_net = QVBoxLayout(group_net)
        layout_net.setContentsMargins(16, 20, 16, 16)
        layout_net.setSpacing(12)
        
        from PyQt6.QtWidgets import QRadioButton, QHBoxLayout
        
        radio_layout = QHBoxLayout()
        rb_lan = QRadioButton("LAN (Сетевой кабель)")
        rb_wifi = QRadioButton("Wi-Fi (Точка доступа KU6)")
        
        if CONNECTION_MODE == "WIFI":
            rb_wifi.setChecked(True)
        else:
            rb_lan.setChecked(True)
            
        radio_layout.addWidget(rb_lan)
        radio_layout.addWidget(rb_wifi)
        layout_net.addLayout(radio_layout)
        
        btn_connect_wifi = QPushButton("Подключиться к Wi-Fi плеера (Автоматически)")
        btn_connect_wifi.setObjectName("btn_ghost")
        
        # Функция для генерации профиля и подключения к Wi-Fi
        def _connect_to_wifi():
            import subprocess
            import tempfile
            import os
            from PyQt6.QtWidgets import QMessageBox
            
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
                
                # Добавляем профиль
                subprocess.run(["netsh", "wlan", "add", "profile", f"filename={xml_path}"], check=True, capture_output=True)
                # Подключаемся
                subprocess.run(["netsh", "wlan", "connect", f"name={ssid}"], check=True, capture_output=True)
                
                QMessageBox.information(dialog, "Подключение", f"Windows отправлена команда на подключение к Wi-Fi: {ssid}.\nПожалуйста, подождите пару секунд, пока Windows установит соединение.")
                rb_wifi.setChecked(True) # Автоматически переключаем режим
            except Exception as e:
                QMessageBox.warning(dialog, "Ошибка", f"Не удалось автоматически подключиться к Wi-Fi. Возможно, программе требуются права Администратора.\n\nВы можете просто подключиться вручную через меню Windows в правом нижнем углу.\n\nКод: {e}")
                
        btn_connect_wifi.clicked.connect(_connect_to_wifi)
        layout_net.addWidget(btn_connect_wifi)
        
        scroll_layout.addWidget(group_net)
        
        # Группа 1: Сетка экранов
        group_grid = QGroupBox("Сетка LED-панелей")
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

        layout_grid.addRow("Ширина 1 панели (px):", spin_w)
        layout_grid.addRow("Высота 1 панели (px):", spin_h)
        layout_grid.addRow("Количество колонок (X):", spin_cols)
        layout_grid.addRow("Количество строк (Y):", spin_rows)
        layout_grid.addRow("Автоопределение сетки по холсту:", chk_auto)
        
        scroll_layout.addWidget(group_grid)
        
        # Группа 2: Оптимизация видео
        group_opt = QGroupBox("Оптимизация видео (FFmpeg)")
        layout_opt = QVBoxLayout(group_opt)
        layout_opt.setContentsMargins(16, 20, 16, 16)
        layout_opt.setSpacing(12)
        
        chk_auto_opt = QCheckBox("Автоматически оптимизировать видео в «Простом режиме»")
        chk_auto_opt.setChecked(AUTO_OPTIMIZE_VIDEO)
        lbl_auto_opt = QLabel("Сжимает видео под размер экрана перед отправкой, чтобы избежать лагов.")
        lbl_auto_opt.setWordWrap(True)
        lbl_auto_opt.setStyleSheet("color: gray; font-size: 11px; margin-left: 24px;")
        
        chk_crush = QCheckBox("Очищать цифровой шум на черном фоне (Crush Blacks)")
        chk_crush.setChecked(CRUSH_BLACKS)
        lbl_crush = QLabel("Обрезает почти черные пиксели до идеального (0,0,0). Убирает синие/зеленые точки.")
        lbl_crush.setWordWrap(True)
        lbl_crush.setStyleSheet("color: gray; font-size: 11px; margin-left: 24px;")
        
        chk_limit = QCheckBox("Оптимизировать битрейт и плавность (GOP 30, Max 4M)")
        chk_limit.setChecked(LIMIT_BITRATE)
        lbl_limit = QLabel("Снижает нагрузку на процессор контроллера. Включите, если видео «подлагивает».")
        lbl_limit.setWordWrap(True)
        lbl_limit.setStyleSheet("color: gray; font-size: 11px; margin-left: 24px;")
        
        layout_opt.addWidget(chk_auto_opt)
        layout_opt.addWidget(lbl_auto_opt)
        layout_opt.addWidget(chk_crush)
        layout_opt.addWidget(lbl_crush)
        layout_opt.addWidget(chk_limit)
        layout_opt.addWidget(lbl_limit)
        
        scroll_layout.addWidget(group_opt)
        
        # Группа 3: Развлечения / Скринсейверы
        group_fun = QGroupBox("Развлечения / Скринсейверы")
        layout_fun = QVBoxLayout(group_fun)
        layout_fun.setContentsMargins(16, 20, 16, 16)
        
        btn_ping_pong = QPushButton("🏓 Запустить заставку Пинг-Понг")
        btn_ping_pong.setObjectName("btn_secondary")
        btn_ping_pong.setMinimumHeight(32)
        
        ping_pong_progress = QProgressBar()
        ping_pong_progress.setTextVisible(False)
        ping_pong_progress.setFixedHeight(4)
        ping_pong_progress.setVisible(False)
        
        def _run_ping_pong():
            btn_ping_pong.setEnabled(False)
            btn_ping_pong.setText("Генерация кадров...")
            ping_pong_progress.setVisible(True)
            ping_pong_progress.setValue(0)
            
            from src.ui.workers import PingPongWorker
            self.ping_pong_worker = PingPongWorker(self.client)
            
            def _on_prog(p):
                ping_pong_progress.setValue(p)
                if p > 50: btn_ping_pong.setText("Сборка видео (FFmpeg)...")
                if p > 80: btn_ping_pong.setText("Отправка на LED-экран...")
                
            def _on_finish(success, msg):
                btn_ping_pong.setEnabled(True)
                btn_ping_pong.setText("🏓 Запустить заставку Пинг-Понг")
                ping_pong_progress.setVisible(False)
                if success:
                    self.log("Пинг-Понг успешно запущен на экране!")
                else:
                    self.log(f"Ошибка Пинг-Понг: {msg}")
                    QMessageBox.warning(dialog, "Ошибка", msg)
            
            self.ping_pong_worker.progress.connect(_on_prog)
            self.ping_pong_worker.finished.connect(_on_finish)
            self.ping_pong_worker.start()
            
        btn_ping_pong.clicked.connect(_run_ping_pong)
        
        layout_fun.addWidget(btn_ping_pong)
        layout_fun.addWidget(ping_pong_progress)
        
        scroll_layout.addWidget(group_fun)
        
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        # Кнопка сохранения всегда внизу, не прокручивается
        btn_save = QPushButton("Сохранить настройки")
        btn_save.setObjectName("btn_primary")
        btn_save.setMinimumHeight(40)
        btn_save.clicked.connect(dialog.accept)
        
        # Контейнер для кнопки с отступами
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
                connection_mode=new_mode
            )
            self.log(f"Настройки сохранены: {spin_cols.value()}x{spin_rows.value()} (Режим: {new_mode})")
            
            # Обновляем адреса клиента и перезапускаем пинг
            base_url, reboot_url = get_current_urls()
            self.client.update_urls(base_url, reboot_url)
            
            # Обновим сетку
            screen_config.update_from_device_info(screen_config.total_width, screen_config.total_height)
            self.scene_editor.refresh_grid()

    # ================================================================
    # ОБРАБОТЧИКИ СОБЫТИЙ: ПРОГРАММЫ (ПЛЕЙЛИСТЫ)
    # ================================================================

    def _refresh_programs_list(self) -> None:
        self.list_programs.blockSignals(True)
        self.list_programs.clear()
        for p in self.playlists_manager.get_all_programs():
            self.list_programs.addItem(p["name"])
        self.list_programs.blockSignals(False)

        # Выбираем первую программу по умолчанию
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
            files = [self.media_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.media_list.count())]
            self.playlists_manager.set_program_files(self.current_program_id, files)

    def _on_program_selected(self) -> None:
        prog_id = self._get_selected_program_id()
        if not prog_id:
            return

        # Сохраняем текущие файлы старой программы перед переключением
        self._save_current_program_files()

        self.current_program_id = prog_id
        
        self.media_list.clear()
        files = self.playlists_manager.get_program_files(prog_id)
        from src.core.config import VIDEO_EXTENSIONS
        for f in files:
            path = Path(f)
            ext = path.suffix.lower()
            icon_str = "🎬" if ext in VIDEO_EXTENSIONS else ""
            item = QListWidgetItem(f"{icon_str}  {path.name}".strip())
            
            # Миниатюра: картинки напрямую, видео/GIF — через FFmpeg
            pixmap = self._get_media_thumbnail(str(path), ext)
            if pixmap:
                item.setIcon(QIcon(pixmap))
            
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            self.media_list.addItem(item)
        
        self.log(f"Выбрана программа: {self.list_programs.currentItem().text()}")

    def _on_add_program(self) -> None:
        name, ok = QInputDialog.getText(self, "Новая программа", "Введите название программы:")
        if ok and name.strip():
            self.playlists_manager.add_program(name.strip())
            self._refresh_programs_list()
            self.list_programs.setCurrentRow(self.list_programs.count() - 1)

    def _on_rename_program(self) -> None:
        prog_id = self._get_selected_program_id()
        if not prog_id:
            return
        current_name = self.list_programs.currentItem().text()
        new_name, ok = QInputDialog.getText(self, "Переименовать", "Новое название:", text=current_name)
        if ok and new_name.strip():
            self.playlists_manager.rename_program(prog_id, new_name.strip())
            self._refresh_programs_list()

    def _on_delete_program(self) -> None:
        prog_id = self._get_selected_program_id()
        if not prog_id:
            return
        if len(self.playlists_manager.get_all_programs()) <= 1:
            QMessageBox.warning(self, "Ошибка", "Нельзя удалить последнюю программу.")
            return

        if self.current_program_id == prog_id:
            self.current_program_id = None
        self.playlists_manager.delete_program(prog_id)
        self._refresh_programs_list()

    # ================================================================
    # ОБРАБОТЧИКИ СОБЫТИЙ: МЕДИА
    # ================================================================

    def _get_media_thumbnail(self, file_path: str, ext: str) -> QPixmap | None:
        """Создаёт миниатюру для медиафайла (картинка, видео или GIF)."""
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
            Qt.TransformationMode.SmoothTransformation
        )

    def open_file_dialog(self) -> None:
        all_exts = " ".join(f"*{ext}" for ext in sorted(ALLOWED_EXTENSIONS))
        files, _ = QFileDialog.getOpenFileNames(self, "Выберите файлы", "", f"Все медиа ({all_exts})")
        if files:
            self.add_media_files(files)

    def add_media_files(self, file_paths: list[str]) -> None:
        existing_paths = {
            self.media_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.media_list.count())
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
                    type_str = "Видео"
                else:
                    icon_str = ""
                    type_str = "Изображение"

                item_text = f"{icon_str}  {path.name}    ({size_str}, {type_str})".strip()
                item = QListWidgetItem(item_text)
                
                # Миниатюра: картинки напрямую, видео/GIF — через FFmpeg
                pixmap = self._get_media_thumbnail(str(path), ext)
                if pixmap:
                    item.setIcon(QIcon(pixmap))
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                item.setToolTip(str(path))
                self.media_list.addItem(item)

                self.log(f"+ Добавлен: {path.name} ({size_str})")
                existing_paths.add(str(path))
                added_count += 1
                
        if added_count > 0:
            self._save_current_program_files()

    def _on_remove_media_item(self, item: QListWidgetItem) -> None:
        """Удаляет файл из локального списка (двойной клик)."""
        row = self.media_list.row(item)
        removed = self.media_list.takeItem(row)
        if removed:
            path = Path(removed.data(Qt.ItemDataRole.UserRole))
            self.log(f"- Удалён из списка: {path.name}")
            self._save_current_program_files()

    def _on_clear_media_list(self) -> None:
        """Очищает весь список медиафайлов."""
        self.media_list.clear()
        self.log("  Список медиа очищен")
        self._save_current_program_files()

    def _on_play_media(self) -> None:
        """
        Запускает двухэтапную загрузку и воспроизведение медиа.

        Собирает пути файлов из списка и передаёт UploadMediaWorker,
        который выполнит: MD5 → checkUpload → uploadMedia → uploadThirdProgram
        в отдельном потоке.
        """
        file_paths = []
        for i in range(self.media_list.count()):
            item = self.media_list.item(i)
            file_paths.append(item.data(Qt.ItemDataRole.UserRole))

        if not file_paths:
            self.log("⚠ Добавьте файлы в медиабиблиотеку")
            return

        # Блокируем кнопку и показываем прогресс
        self.btn_play_media.setEnabled(False)
        self.btn_play_media.setText("⏳  Загрузка...")
        self.upload_progress.setVisible(True)
        self.upload_progress.setValue(0)
        self.btn_cancel_upload.setVisible(True)
        self.btn_cancel_upload.setEnabled(True)
        self.btn_cancel_upload.setText("Отмена")

        # Создаём рабочий поток для загрузки
        from src.ui.workers import UploadMediaWorker
        worker = UploadMediaWorker(
            client=self.client, 
            file_paths=file_paths,
            image_duration_sec=self.spin_image_duration.value()
        )
        worker.progress.connect(self.upload_progress.setValue)
        worker.finished.connect(self._on_media_upload_finished)
        worker.finished.connect(lambda *args: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

        self.log(f"→ Загрузка {len(file_paths)} файлов на устройство...")

    def _on_cancel_upload(self) -> None:
        """Обработчик отмены текущей загрузки."""
        self.btn_cancel_upload.setEnabled(False)
        self.btn_cancel_upload.setText("Отменяем...")
        self.log("⚠ Остановка загрузки...")
        
        from src.ui.workers import UploadMediaWorker
        for w in self._active_workers:
            if isinstance(w, UploadMediaWorker):
                w._is_aborted = True
                
        # Принудительно обрываем HTTP-соединение
        self.client.abort_all_requests()

    def _on_media_upload_finished(self, success: bool, message: str) -> None:
        """Обработчик завершения загрузки медиа."""
        self.btn_play_media.setEnabled(True)
        self.btn_play_media.setText("▶  Воспроизвести на LED")
        self.btn_cancel_upload.setVisible(False)

        if success:
            self.upload_progress.setValue(100)
            self.log(f"✓ {message}")
            # Скрываем прогресс через 2 секунды
            QTimer.singleShot(2000, lambda: self.upload_progress.setVisible(False))
        else:
            self.upload_progress.setVisible(False)
            self.log(f"✗ {message}")

    # ================================================================
    # ОБРАБОТЧИКИ СОБЫТИЙ: ЯРКОСТЬ
    # ================================================================

    def _on_brightness_changed(self, value: int) -> None:
        """
        Обработчик изменения слайдера яркости.

        Использует debounce-паттерн: при каждом движении слайдера
        перезапускается таймер. HTTP-запрос отправляется только когда
        пользователь остановил ползунок (пауза ≥ BRIGHTNESS_DEBOUNCE_MS).

        Это предотвращает спам устройства сотнями запросов при
        плавном перетаскивании слайдера.
        """
        self._pending_brightness = value
        self.brightness_value_label.setText(f"{value}%")

        # Перезапускаем таймер (каждое движение сбрасывает countdown)
        self._brightness_timer.start()

    def _send_brightness(self) -> None:
        """Отправляет значение яркости на устройство (вызывается по таймеру)."""
        value = self._pending_brightness

        worker = BrightnessWorker(client=self.client, value=value)
        worker.finished.connect(self._on_brightness_sent)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_brightness_sent(self, success: bool, message: str) -> None:
        """Обработчик завершения отправки яркости."""
        if success:
            self.log(f"☀ {message}")
        else:
            self.log(f"✗ {message}")

    # ================================================================
    # ОБРАБОТЧИКИ СОБЫТИЙ: УПРАВЛЕНИЕ
    # ================================================================

    def _on_toggle_screen(self) -> None:
        """Переключает состояние экрана (ВКЛ/ВЫКЛ)."""
        # Инвертируем текущее состояние
        new_state = not self._screen_on

        self.btn_screen_power.setEnabled(False)

        worker = ScreenPowerWorker(client=self.client, power_on=new_state)
        worker.finished.connect(lambda ok, msg: self._on_screen_toggled(ok, msg, new_state))
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_screen_toggled(self, success: bool, message: str, new_state: bool) -> None:
        """Обработчик завершения переключения экрана."""
        self.btn_screen_power.setEnabled(True)
        if success:
            self._screen_on = new_state
            self.log(f"⏻ {message}")
        else:
            self.log(f"✗ {message}")

    def _on_reboot(self) -> None:
        """Перезагружает устройство (с подтверждением)."""
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Вы уверены, что хотите перезагрузить медиаплеер?\n"
            "Воспроизведение контента будет прервано.",
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
        """Обработчик завершения перезагрузки."""
        self.btn_reboot.setEnabled(True)
        if success:
            self.log(f"↻ {message}")
        else:
            self.log(f"✗ {message}")

    def _on_clear_memory(self) -> None:
        """Показывает предупреждение и запускает процесс удаления всех медиа."""
        reply = QMessageBox.question(
            self, 
            "Очистка памяти", 
            "Вы уверены, что хотите удалить ВСЕ файлы с плеера? Это освободит память, но при следующем воспроизведении файлы загрузятся заново.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        self.btn_clear_memory.setEnabled(False)
        self.btn_clear_memory.setText("⏳  Очистка...")
        
        from src.ui.workers import ClearMemoryWorker
        worker = ClearMemoryWorker(self.client)
        worker.progress.connect(lambda p: self.log(f"  Удаление файлов: {p}%"))
        worker.finished.connect(self._on_clear_memory_finished)
        worker.finished.connect(lambda *args: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()
        
        self.log("Начата очистка памяти плеера...")

    def _on_clear_memory_finished(self, success: bool, message: str) -> None:
        """Обработчик завершения очистки памяти."""
        self.btn_clear_memory.setEnabled(True)
        self.btn_clear_memory.setText("🗑  Очистить память")
        
        if success:
            self.log(f"✓ {message}")
            QMessageBox.information(self, "Успех", message)
        else:
            self.log(f"✗ {message}")
            QMessageBox.critical(self, "Ошибка", message)

    def _on_show_device_media(self) -> None:
        """Показывает менеджер файлов устройства."""
        dialog = DeviceMediaDialog(self, self.client, self.playlists_manager)
        dialog.exec()

    # ================================================================
    # УТИЛИТЫ
    # ================================================================

    def log(self, message: str) -> None:
        """
        Добавляет сообщение в лог-панель с временной меткой.

        Args:
            message: Текст сообщения для отображения.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_panel.append(f"[{timestamp}]  {message}")
        # Автоматическая прокрутка вниз
        scrollbar = self.log_panel.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Форматирует размер файла в человеко-читаемый вид."""
        if size_bytes < 1024:
            return f"{size_bytes} Б"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} КБ"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} МБ"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} ГБ"

    def _cleanup_worker(self, worker) -> None:
        """Удаляет завершённый воркер из списка активных потоков."""
        try:
            self._active_workers.remove(worker)
        except ValueError:
            pass

    # ================================================================
    # ЖИЗНЕННЫЙ ЦИКЛ
    # ================================================================

    def closeEvent(self, event) -> None:
        """Очистка при закрытии окна."""
        # Очищаем ресурсы динамического видеоплеера
        if hasattr(self, "tab_dynamic_video"):
            self.tab_dynamic_video.cleanup()

        # Принудительно обрываем все сетевые соединения, 
        # чтобы потоки, зависшие на HTTP POST, могли завершиться
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
                
        # Ожидаем завершения рендера, если он запущен
        if hasattr(self, "scene_editor") and hasattr(self.scene_editor, "worker") and self.scene_editor.worker:
            try:
                if self.scene_editor.worker.isRunning():
                    self.scene_editor.worker.wait(3000)
            except RuntimeError:
                pass

        event.accept()

    # ================================================================
    # ИНТЕГРАЦИЯ SCENE EDITOR И FFMPEG
    # ================================================================
    
    def _on_render_completed(self, file_path: str) -> None:
        """Срабатывает после успешного рендера сложной сцены в SceneEditor."""
        from datetime import datetime
        name = f"Сцена {datetime.now().strftime('%H:%M:%S')}"
        
        # Создаем плейлист
        prog = self.playlists_manager.add_program(name)
        self.playlists_manager.set_program_files(prog["id"], [file_path])
        
        self.log(f"✦ Создан новый плейлист '{name}' с готовой сценой")
        
        self._refresh_programs_list()
        
        # Находим и выбираем этот плейлист в UI
        items = self.list_programs.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self.list_programs.setCurrentItem(items[0])
            
        # Запускаем отправку
        self._on_play_media()
