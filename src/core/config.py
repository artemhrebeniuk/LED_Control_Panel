# -*- coding: utf-8 -*-
from __future__ import annotations
"""
config.py — Centralized configuration for LED display matrix and network parameters.

This module contains ALL configurable parameters of the system.

SCREEN RESOLUTION is determined in two ways:
  1. Automatic — on startup, the application requests GET /device
     from the player and receives the actual screenWidth/screenHeight.
     From these, SCREEN_COLS and SCREEN_ROWS are dynamically computed.
  2. Manual (fallback) — if the device is offline, default values
     SCREEN_COLS=2, SCREEN_ROWS=2 are utilized.

The ScreenConfig class maintains runtime state and allows updating
dimensions dynamically (e.g., following device reconnection).
"""

import json
import os

# ====================================================================
# PHYSICAL PARAMETERS OF A SINGLE LED MODULE
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
# DEFAULT GRID CONFIGURATION (Fallback when offline)
# ====================================================================
DEFAULT_SCREEN_COLS: int = 2     # Number of horizontal panels
DEFAULT_SCREEN_ROWS: int = 2     # Number of vertical panels

# ====================================================================
# DEVICE NETWORK PARAMETERS
# ====================================================================
LAN_IP: str = "169.254.250.250"       # Default IP for direct Ethernet cable (APIPA)
WIFI_IP: str = "192.168.43.1"         # Default IP for Kystar KD6 Wi-Fi AP

DEVICE_IP: str = WIFI_IP if CONNECTION_MODE == "WIFI" else LAN_IP
API_PORT: int = 18080                 # Primary HTTP API port
REBOOT_PORT: int = 18081              # Port for device reboot commands

BASE_URL: str = f"http://{DEVICE_IP}:{API_PORT}"
REBOOT_URL: str = f"http://{DEVICE_IP}:{REBOOT_PORT}"

def get_current_urls():
    """Returns active URLs based on selected connection mode."""
    ip = WIFI_IP if CONNECTION_MODE == "WIFI" else LAN_IP
    return f"http://{ip}:{API_PORT}", f"http://{ip}:{REBOOT_PORT}"

# ====================================================================
# TIMEOUTS & INTERVALS
# ====================================================================
HTTP_TIMEOUT: int = 10               # HTTP request timeout in seconds
PING_INTERVAL_MS: int = 5000         # Device ping heartbeat interval (ms)
BRIGHTNESS_DEBOUNCE_MS: int = 300    # Brightness slider debounce delay (ms)

# ====================================================================
# MEDIA FILE TYPES
# ====================================================================
MEDIA_TYPE_VIDEO: int = 1
MEDIA_TYPE_IMAGE: int = 2

VIDEO_EXTENSIONS: set[str] = {".mp4", ".avi", ".mov", ".mkv", ".rmvb", ".3gp", ".flv", ".wmv"}
IMAGE_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

DEFAULT_IMAGE_DURATION_MS: int = 10000  # 10 seconds

ALLOWED_EXTENSIONS: set[str] = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS


class ScreenConfig:
    """
    Dynamic screen configuration updated at runtime.

    During startup and periodically (via PingWorker), the application queries
    receiver card information from the player (GET /getCardInfo).
    
    rxNum represents connected receiving cards (modules).
    Since column count is configured (e.g., SCREEN_COLS = 2), rows are
    derived as rxNum // SCREEN_COLS.

    If the device is offline or reports 0 cards, fallback defaults are used.
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
        Updates configuration based on actual canvas bounds (OS Canvas)
        and number of connected receiving cards (rx_num).
        """
        if not AUTO_GRID:
            # Manual mode: fixed layout grid
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
                
                # Dynamic grid layout calculation based on active cards
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
        """Returns textual description of current display matrix."""
        source = "auto" if self._auto_detected else "default"
        return (
            f"Grid: {self._cols}×{self._rows} "
            f"({self._total_width}×{self._total_height} px) • "
            f"Modules: ~{self._connected_modules} ({source})"
        )


# ====================================================================
# GLOBAL SCREEN CONFIGURATION SINGLETON
# All modules reference this single instance.
# ====================================================================
screen_config = ScreenConfig()


def get_media_type(file_extension: str) -> int | None:
    """
    Determines media type based on file extension.

    Args:
        file_extension: File extension including leading dot (e.g., '.mp4').

    Returns:
        1 for video, 2 for image, None if unknown.
    """
    ext = file_extension.lower()
    if ext in VIDEO_EXTENSIONS:
        return MEDIA_TYPE_VIDEO
    if ext in IMAGE_EXTENSIONS:
        return MEDIA_TYPE_IMAGE
    return None


def get_screen_payload(extra_params: dict | None = None) -> dict:
    """
    Constructs base JSON payload with current screen dimensions for API requests.

    Uses active values from screen_config (which may be updated via auto-detection).

    Args:
        extra_params: Additional parameters to include in the payload.

    Returns:
        Dictionary with width, height, and any additional parameters.
    """
    payload: dict = {
        "width": screen_config.total_width,
        "height": screen_config.total_height,
    }
    if extra_params:
        payload.update(extra_params)
    return payload
