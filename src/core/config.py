# -*- coding: utf-8 -*-
"""
config.py — Централизованная конфигурация LED-экрана и сетевых параметров.

Этот модуль содержит ВСЕ настраиваемые параметры системы.

РАЗРЕШЕНИЕ ЭКРАНА определяется двумя способами:
  1. Автоматически — при запуске приложение запрашивает GET /device
     у плеера и получает реальные screenWidth/screenHeight. Из них
     обратно вычисляются SCREEN_COLS и SCREEN_ROWS.
  2. Вручную (fallback) — если устройство недоступно, используются
     значения по умолчанию SCREEN_COLS=2, SCREEN_ROWS=2.

Класс ScreenConfig хранит текущее состояние и позволяет обновлять
размеры в рантайме (например, после переподключения устройства).
"""

import json
import os

# ====================================================================
# ФИЗИЧЕСКИЕ ПАРАМЕТРЫ ОДНОГО LED-МОДУЛЯ
# ====================================================================
HARDWARE_CONFIG_FILE = "data/hardware_config.json"

def _load_hardware_config():
    if os.path.exists(HARDWARE_CONFIG_FILE):
        try:
            with open(HARDWARE_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return (
                    data.get("PANEL_WIDTH", 80), 
                    data.get("PANEL_HEIGHT", 40),
                    data.get("SCREEN_COLS", 2),
                    data.get("SCREEN_ROWS", 2),
                    data.get("AUTO_GRID", True),
                    data.get("AUTO_OPTIMIZE_VIDEO", False),
                    data.get("CRUSH_BLACKS", False),
                    data.get("LIMIT_BITRATE", False),
                    data.get("CONNECTION_MODE", "LAN")
                )
        except Exception:
            pass
    return 80, 40, 2, 2, True, False, False, False, "LAN"

PANEL_WIDTH, PANEL_HEIGHT, SCREEN_COLS, SCREEN_ROWS, AUTO_GRID, AUTO_OPTIMIZE_VIDEO, CRUSH_BLACKS, LIMIT_BITRATE, CONNECTION_MODE = _load_hardware_config()

def save_hardware_config(width: int, height: int, cols: int, rows: int, auto_grid: bool, 
                         auto_optimize: bool = None, crush_blacks: bool = None, limit_bitrate: bool = None,
                         connection_mode: str = None) -> None:
    global PANEL_WIDTH, PANEL_HEIGHT, SCREEN_COLS, SCREEN_ROWS, AUTO_GRID
    global AUTO_OPTIMIZE_VIDEO, CRUSH_BLACKS, LIMIT_BITRATE, CONNECTION_MODE
    
    PANEL_WIDTH = width
    PANEL_HEIGHT = height
    SCREEN_COLS = cols
    SCREEN_ROWS = rows
    AUTO_GRID = auto_grid
    if auto_optimize is not None: AUTO_OPTIMIZE_VIDEO = auto_optimize
    if crush_blacks is not None: CRUSH_BLACKS = crush_blacks
    if limit_bitrate is not None: LIMIT_BITRATE = limit_bitrate
    if connection_mode is not None: CONNECTION_MODE = connection_mode
    
    try:
        with open(HARDWARE_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "PANEL_WIDTH": PANEL_WIDTH, 
                "PANEL_HEIGHT": PANEL_HEIGHT,
                "SCREEN_COLS": SCREEN_COLS,
                "SCREEN_ROWS": SCREEN_ROWS,
                "AUTO_GRID": AUTO_GRID,
                "AUTO_OPTIMIZE_VIDEO": AUTO_OPTIMIZE_VIDEO,
                "CRUSH_BLACKS": CRUSH_BLACKS,
                "LIMIT_BITRATE": LIMIT_BITRATE,
                "CONNECTION_MODE": CONNECTION_MODE
            }, f)
    except Exception:
        pass


# ====================================================================
# КОНФИГУРАЦИЯ СЕТКИ ПО УМОЛЧАНИЮ (используется если устройство оффлайн)
# ====================================================================
DEFAULT_SCREEN_COLS: int = 2     # Количество панелей по горизонтали
DEFAULT_SCREEN_ROWS: int = 2     # Количество панелей по вертикали

# ====================================================================
# СЕТЕВЫЕ ПАРАМЕТРЫ УСТРОЙСТВА
# ====================================================================
LAN_IP: str = "169.254.250.250"       # IP-адрес по умолчанию для кабеля (APIPA)
WIFI_IP: str = "192.168.43.1"         # IP-адрес по умолчанию для Wi-Fi AP Kystar KD6

DEVICE_IP: str = WIFI_IP if CONNECTION_MODE == "WIFI" else LAN_IP
API_PORT: int = 18080                 # Основной порт API
REBOOT_PORT: int = 18081              # Порт для команды перезагрузки

BASE_URL: str = f"http://{DEVICE_IP}:{API_PORT}"
REBOOT_URL: str = f"http://{DEVICE_IP}:{REBOOT_PORT}"

def get_current_urls():
    """Возвращает актуальные URL на основе выбранного режима."""
    ip = WIFI_IP if CONNECTION_MODE == "WIFI" else LAN_IP
    return f"http://{ip}:{API_PORT}", f"http://{ip}:{REBOOT_PORT}"

# ====================================================================
# ТАЙМАУТЫ И ИНТЕРВАЛЫ
# ====================================================================
HTTP_TIMEOUT: int = 10               # Таймаут HTTP-запросов в секундах
PING_INTERVAL_MS: int = 5000         # Интервал пинга устройства (мс)
BRIGHTNESS_DEBOUNCE_MS: int = 300    # Задержка отправки яркости (мс)

# ====================================================================
# ТИПЫ МЕДИАФАЙЛОВ
# ====================================================================
MEDIA_TYPE_VIDEO: int = 1
MEDIA_TYPE_IMAGE: int = 2

VIDEO_EXTENSIONS: set[str] = {".mp4", ".avi", ".mov", ".mkv", ".rmvb", ".3gp", ".flv", ".wmv"}
IMAGE_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

DEFAULT_IMAGE_DURATION_MS: int = 10000  # 10 секунд

ALLOWED_EXTENSIONS: set[str] = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS


class ScreenConfig:
    """
    Динамическая конфигурация экрана, обновляемая в рантайме.

    При запуске и периодически (через PingWorker) приложение запрашивает
    у плеера информацию о картах (GET /getCardInfo).
    
    rxNum — количество подключенных приёмных карт (модулей).
    Поскольку ширина фиксирована (SCREEN_COLS = 2), мы вычисляем количество
    рядов как rxNum // SCREEN_COLS.

    Если устройство недоступно или возвращает 0 карт, используются значения по умолчанию.
    """

    def __init__(self) -> None:
        self._cols: int = SCREEN_COLS
        self._rows: int = SCREEN_ROWS
        self._total_width: int = PANEL_WIDTH * self._cols
        self._total_height: int = PANEL_HEIGHT * self._rows
        self._auto_detected: bool = False
        self._connected_modules: int = 0

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def total_width(self) -> int:
        return self._total_width

    @property
    def total_height(self) -> int:
        return self._total_height

    @property
    def auto_detected(self) -> bool:
        return self._auto_detected

    @property
    def connected_modules(self) -> int:
        return self._connected_modules

    def update_from_device_info(self, screen_width: int, screen_height: int, rx_num: int = 0) -> bool:
        """
        Обновляет конфигурацию на основе реального разрешения холста (OS Canvas)
        и количества подключенных приемных карт (rx_num).
        """
        if not AUTO_GRID:
            # Ручной режим: сетка фиксирована
            new_auto = False
            new_cols = SCREEN_COLS
            new_rows = SCREEN_ROWS
            new_width = new_cols * PANEL_WIDTH
            new_height = new_rows * PANEL_HEIGHT
        else:
            if screen_width <= 0 or screen_height <= 0:
                new_auto = False
                new_cols = SCREEN_COLS
                new_rows = SCREEN_ROWS
                new_width = new_cols * PANEL_WIDTH
                new_height = new_rows * PANEL_HEIGHT
            else:
                new_auto = True
                self._connected_modules = rx_num if rx_num > 0 else SCREEN_COLS * SCREEN_ROWS
                
                # Умный расчет сетки на основе количества активных карт
                if rx_num > 0:
                    new_rows = SCREEN_ROWS
                    new_cols = max(1, (rx_num + new_rows - 1) // new_rows)
                else:
                    new_cols = SCREEN_COLS
                    new_rows = SCREEN_ROWS
                    
                new_width = new_cols * PANEL_WIDTH
                new_height = new_rows * PANEL_HEIGHT

        changed = (
            new_cols != self._cols
            or new_rows != self._rows
            or new_width != self._total_width
            or new_height != self._total_height
            or new_auto != self._auto_detected
        )

        self._cols = new_cols
        self._rows = new_rows
        self._total_width = new_width
        self._total_height = new_height
        self._auto_detected = new_auto

        return changed

    def get_grid_text(self) -> str:
        """Возвращает текстовое описание текущей сетки."""
        source = "авто" if self._auto_detected else "по умолчанию"
        return (
            f"Сетка: {self._cols}×{self._rows} "
            f"({self._total_width}×{self._total_height} px) • "
            f"Модулей: ~{self._connected_modules} ({source})"
        )


# ====================================================================
# ГЛОБАЛЬНЫЙ СИНГЛТОН КОНФИГУРАЦИИ ЭКРАНА
# Все модули используют этот единственный экземпляр.
# ====================================================================
screen_config = ScreenConfig()


def get_media_type(file_extension: str) -> int | None:
    """
    Определяет тип медиафайла по расширению.

    Args:
        file_extension: Расширение файла с точкой (например, '.mp4').

    Returns:
        1 для видео, 2 для изображения, None если тип неизвестен.
    """
    ext = file_extension.lower()
    if ext in VIDEO_EXTENSIONS:
        return MEDIA_TYPE_VIDEO
    if ext in IMAGE_EXTENSIONS:
        return MEDIA_TYPE_IMAGE
    return None


def get_screen_payload(extra_params: dict | None = None) -> dict:
    """
    Формирует базовый JSON-payload с текущими размерами экрана для API.

    Использует актуальные значения из screen_config (которые могут
    быть обновлены автодетектом с устройства).

    Args:
        extra_params: Дополнительные параметры для включения в payload.

    Returns:
        Словарь с ключами width, height и любыми дополнительными параметрами.
    """
    payload: dict = {
        "width": screen_config.total_width,
        "height": screen_config.total_height,
    }
    if extra_params:
        payload.update(extra_params)
    return payload
