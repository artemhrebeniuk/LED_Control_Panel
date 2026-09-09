# -*- coding: utf-8 -*-
from __future__ import annotations
"""
kystar_client.py — Pure API client for Kystar KD6 media player.

This module contains ONLY networking and protocol logic:
- HTTP GET/POST requests to device
- MD5 file hashing and checksum calculation
- Two-stage media upload protocol
- Construction of JSON payloads for API

Contains no PyQt6 or UI logic. All methods are synchronous (blocking)
and must be executed within background QThread workers to prevent UI freezes.
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable

import requests

from src.core.config import (
    ALLOWED_EXTENSIONS,
    BASE_URL,
    DEFAULT_IMAGE_DURATION_MS,
    HTTP_TIMEOUT,
    MEDIA_TYPE_IMAGE,
    MEDIA_TYPE_VIDEO,
    REBOOT_URL,
    get_media_type,
    screen_config,
)

logger = logging.getLogger(__name__)


class KystarClientError(Exception):
    """Base exception for Kystar API client errors."""


class KystarClient:
    """
    Synchronous HTTP client for managing Beijing Kystar KD6 media players.

    All methods perform blocking HTTP requests using the requests library.
    For PyQt6 integration, invoke these methods ONLY from worker QThreads.

    Attributes:
        base_url: Base API URL (http://IP:18080).
        reboot_url: Hardware reboot URL (http://IP:18081).
        timeout: HTTP request timeout in seconds.
        session: Persistent requests.Session for TCP keep-alive connections.
    """

    def __init__(
        self,
        base_url: str = None,
        reboot_url: str = None,
        timeout: int = HTTP_TIMEOUT,
    ) -> None:
        from src.core.config import get_current_urls
        default_base, default_reboot = get_current_urls()
        self.base_url = base_url or default_base
        self.reboot_url = reboot_url or default_reboot
        self.timeout = timeout
        self.session = requests.Session()

    def __del__(self) -> None:
        """Closes HTTP session when object is destroyed."""
        try:
            self.session.close()
        except Exception:
            pass

    def update_urls(self, base_url: str, reboot_url: str) -> None:
        """Updates communication URLs for device connection."""
        self.base_url = base_url
        self.reboot_url = reboot_url
        self.abort_all_requests()

    def abort_all_requests(self) -> None:
        """
        Forces all active HTTP connections to terminate.
        Used to abort uploads immediately when switching modes or closing app.
        """
        try:
            self.session.close()
            self.session = requests.Session()
        except Exception as e:
            logger.debug("Error while aborting requests: %s", e)

    # ================================================================
    # HELPER HTTP METHODS
    # ================================================================

    def _get(self, endpoint: str, url_base: str | None = None, **kwargs) -> dict[str, Any]:
        """
        Performs HTTP GET request to player API.

        Args:
            endpoint: API path (e.g. '/device').
            url_base: Optional alternate base URL (e.g. port 18081 for reboot).
            **kwargs: Extra arguments for requests.get().

        Returns:
            Parsed JSON response dictionary.

        Raises:
            KystarClientError: On connection failure, timeout, or invalid JSON.
        """
        base = url_base or self.base_url
        url = f"{base}/{endpoint.lstrip('/')}"
        try:
            response = self.session.get(url, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            raise KystarClientError(f"No connection to device: {e}") from e
        except requests.exceptions.Timeout as e:
            raise KystarClientError(f"Request timeout to {url}: {e}") from e
        except requests.exceptions.RequestException as e:
            raise KystarClientError(f"HTTP request error: {e}") from e
        except json.JSONDecodeError as e:
            raise KystarClientError(f"Invalid JSON in response: {e}") from e

    def _post(self, endpoint: str, params: dict | None = None,
              data: Any = None, files: dict | None = None,
              json_data: Any = None, **kwargs) -> dict[str, Any]:
        """
        Performs HTTP POST request to player API.

        Args:
            endpoint: API endpoint path.
            params: Query parameters (?key=value).
            data: Form-encoded request body.
            files: Multipart upload file payload.
            json_data: JSON payload.
            **kwargs: Extra arguments for requests.post().

        Returns:
            Parsed JSON response dictionary.

        Raises:
            KystarClientError: On network errors or invalid responses.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.session.post(
                url,
                params=params,
                data=data,
                files=files,
                json=json_data,
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            raise KystarClientError(f"No connection to device: {e}") from e
        except requests.exceptions.Timeout as e:
            raise KystarClientError(f"Request timeout to {url}: {e}") from e
        except requests.exceptions.RequestException as e:
            raise KystarClientError(f"HTTP request error: {e}") from e
        except json.JSONDecodeError as e:
            raise KystarClientError(f"Invalid JSON in response: {e}") from e

    # ================================================================
    # DEVICE TELEMETRY & STATUS
    # ================================================================

    def ping(self) -> bool:
        """
        Checks device connectivity over the network.
        Sends GET /device with a short 2-second timeout.
        Used by background PingWorker to update UI connection indicator.
        """
        try:
            response = self.session.get(
                f"{self.base_url}/device",
                timeout=2,
            )
            data = response.json()
            return data.get("code") == 200
        except Exception:
            return False

    def get_device_info(self) -> dict[str, Any]:
        """
        Retrieves comprehensive hardware device information.
        Endpoint: GET /device

        Returns:
            Dictionary with appVersion, deviceName, screenWidth,
            screenHeight, usableSpace, totalSpace, etc.
        """
        result = self._get("device")
        return result.get("data", result)

    def get_screen_params(self) -> dict[str, Any]:
        """
        Retrieves current screen parameters (brightness, audio, power state).
        Endpoint: GET /getScreenParams

        Returns:
            Dictionary with bright (0-100), voice (0-1), screenOn (bool), contrast (int).
        """
        return self._get("getScreenParams")

    # ================================================================
    # SCREEN CONTROLS
    # ================================================================

    def set_brightness(self, value: int) -> dict[str, Any]:
        """
        Sets screen brightness level.
        Endpoint: POST /setting/bright?bright=N

        Args:
            value: Brightness percentage from 0 (black) to 100 (maximum).
        """
        value = max(0, min(100, value))
        logger.info("Setting screen brightness: %d%%", value)
        return self._post("setting/bright", params={"bright": value})

    def set_screen_power(self, on: bool) -> dict[str, Any]:
        """
        Enables or disables screen output (power toggle).
        Endpoint: POST /setting/screen?screen=true|false
        """
        screen_value = "true" if on else "false"
        logger.info("Screen power set to: %s", "ON" if on else "OFF")
        return self._post("setting/screen", params={"screen": screen_value})

    def reboot(self) -> dict[str, Any]:
        """
        Reboots the media player hardware.
        Endpoint: GET :18081/reboot (Notice: dedicated port 18081).
        """
        logger.warning("Hardware reboot command dispatched to player")
        return self._get("reboot", url_base=self.reboot_url)

    # ================================================================
    # MEDIA FILES: TWO-STAGE UPLOAD PROTOCOL
    # ================================================================

    @staticmethod
    def calculate_md5_and_length(file_path: str) -> str:
        """
        Calculates md5AndLength string identifier according to Kystar SDK protocol.

        Specification:
        1. Read the first 1 MB (1024 * 1024 bytes) of the file (or full file if < 1 MB).
        2. Compute MD5 checksum of this chunk.
        3. Format string: "{md5_hex}-{full_file_size_in_bytes}".

        Args:
            file_path: Path to target media file.

        Returns:
            Identifier string (e.g. 'dddae1f8cb4bdc55b88f6d03edfc6ac2-952324').
        """
        file_size = os.path.getsize(file_path)
        chunk_size = 1024 * 1024  # 1 MB
        md5_hash = hashlib.md5()

        with open(file_path, "rb") as f:
            chunk = f.read(chunk_size)
            md5_hash.update(chunk)

        md5_hex = md5_hash.hexdigest()
        md5_and_length = f"{md5_hex}-{file_size}"
        logger.debug("MD5 calculated: %s for %s", md5_and_length, file_path)
        return md5_and_length

    def check_upload(self, md5_and_length: str) -> bool:
        """
        Verifies if file is already cached in player storage.
        Endpoint: POST /checkUpload?md5andlength=X

        Returns:
            True if cached on player (code=200), False if missing (code=406).
        """
        try:
            result = self._post("checkUpload", params={"md5andlength": md5_and_length})
            exists = result.get("code") == 200
            logger.info("File check %s: %s", md5_and_length, "EXISTS" if exists else "NOT FOUND")
            return exists
        except KystarClientError:
            return False

    def get_all_media(self) -> list[dict[str, Any]]:
        """
        Lists all media files stored on the player device.
        Endpoint: GET /medias
        """
        try:
            result = self._get("medias")
            return result.get("data", [])
        except KystarClientError as e:
            logger.debug("Error fetching media list: %s", e)
            return []

    def delete_media(self, md5_and_length: str) -> tuple[bool, str]:
        """
        Deletes media file from player storage.
        Endpoint: POST /deleteMedia?md5AndLength={md5_and_length}
        """
        try:
            result = self._post("deleteMedia", params={"md5AndLength": md5_and_length})
            code = result.get("code")
            if code == 200:
                logger.info("File deleted from player: %s", md5_and_length)
                return True, "Success"
            elif code == 501:
                return False, "File is currently in playback"
            else:
                msg = result.get("message", "Unknown error")
                return False, msg
        except KystarClientError as e:
            logger.debug("Error deleting file %s: %s", md5_and_length, e)
            return False, str(e)

    def upload_media(
        self,
        file_path: str,
        progress_callback: Any = None,
    ) -> str:
        """
        Uploads local media file to the player device.

        Protocol Steps:
        1. Calculate md5AndLength.
        2. Query checkUpload to skip redundant transmission if already cached.
        3. If missing, upload via multipart POST /uploadMedia/{type}/{md5_and_length}.

        Returns:
            md5AndLength identifier string.
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        media_type = get_media_type(extension)
        if media_type is None:
            raise ValueError(f"Unsupported media extension: {extension}")

        if progress_callback:
            progress_callback(10)
        md5_and_length = self.calculate_md5_and_length(file_path)

        if progress_callback:
            progress_callback(20)
        if self.check_upload(md5_and_length):
            logger.info("File already present on player: %s", md5_and_length)
            if progress_callback:
                progress_callback(100)
            return md5_and_length

        if progress_callback:
            progress_callback(30)

        endpoint = f"uploadMedia/{media_type}/{md5_and_length}"
        url = f"{self.base_url}/{endpoint}"
        logger.info("Uploading media: %s → %s", path.name, url)

        file_size = os.path.getsize(file_path)
        upload_timeout = max(self.timeout, file_size // (100 * 1024) + 30)

        try:
            with open(file_path, "rb") as f:
                files = {"file": (path.name, f)}
                response = self.session.post(
                    url,
                    files=files,
                    timeout=upload_timeout,
                )
                response.raise_for_status()
                result = response.json()

            if progress_callback:
                progress_callback(90)

            if result.get("code") != 200:
                raise KystarClientError(
                    f"Upload failed: code={result.get('code')}, message={result.get('message')}"
                )

            logger.info("File upload succeeded: %s", md5_and_length)
            if progress_callback:
                progress_callback(100)
            return md5_and_length

        except requests.exceptions.RequestException as e:
            raise KystarClientError(f"Upload error: {e}") from e

    def stop_playback(self) -> bool:
        """
        Halts active playback on the display.
        Uses playText with empty text which, per Kystar SDK, automatically
        cancels active program playback and releases file handles.
        """
        try:
            params = {
                "text": " ",
                "width": screen_config.total_width,
                "height": screen_config.total_height,
                "scrollSpeed": 1,
                "color": -1,
                "backgroundColor": 0,
                "fontSize": 10
            }
            logger.info("Stopping playback (via playText flush)")
            result = self._post("playText", params=params)
            return result.get("code") == 200
        except Exception as e:
            logger.warning(f"Failed to stop playback: {e}")
            return False

    def upload_third_program(
        self,
        media_items: list[dict[str, Any]],
        program_name: str = "PyQt6 Program",
    ) -> dict[str, Any]:
        """
        Creates and immediately launches a broadcast program with media items.
        Endpoint: POST /uploadThirdProgram

        Args:
            media_items: List of dictionaries with keys:
                - md5AndLength (str)
                - duration (int, ms)
                - anim (str, optional)
            program_name: Program label.
        """
        program_data = {
            "name": program_name,
            "width": screen_config.total_width,
            "height": screen_config.total_height,
            "mediaList": media_items,
        }

        logger.info(
            "Deploying program '%s' with %d media elements",
            program_name,
            len(media_items),
        )

        return self._post("uploadThirdProgram", json_data=program_data)

    def play_media_files(
        self,
        file_paths: list[str],
        image_duration_sec: int = 10,
        progress_callback: Callable[[int], None] | None = None,
    ) -> dict[str, Any]:
        """
        Orchestrates complete media upload and playback sequence.
        """
        media_list: list[dict[str, Any]] = []
        total_files = len(file_paths)

        for idx, file_path in enumerate(file_paths):
            path = Path(file_path)
            extension = path.suffix.lower()
            media_type = get_media_type(extension)

            if media_type is None:
                logger.warning("Skipping unsupported media file: %s", file_path)
                continue

            base_progress = int((idx / total_files) * 80)

            def file_progress(p: int, _base: int = base_progress) -> None:
                if progress_callback:
                    overall = _base + int((p / 100) * (80 / total_files))
                    progress_callback(min(overall, 80))

            md5_and_length = self.upload_media(file_path, progress_callback=file_progress)

            if media_type == MEDIA_TYPE_IMAGE:
                duration = image_duration_sec * 1000
            else:
                duration = 0

            media_list.append({
                "md5AndLength": md5_and_length,
                "duration": duration,
                "anim": "NONE",
            })

        if not media_list:
            raise KystarClientError("No valid media files found for playback")

        if progress_callback:
            progress_callback(85)

        result = self.upload_third_program(media_list)

        if progress_callback:
            progress_callback(100)

        return result

    def set_input_source(self, source_type: int, width: int = 1920, height: int = 1080) -> bool:
        """
        Switches video input feed (HDMI vs. Internal Android player).
        
        Args:
            source_type: 2 (Android/Internal Media Player), 3 (HDMI/External input).
        """
        try:
            params = {
                "status": 1,
                "startX": 0,
                "startY": 0,
                "width": width,
                "height": height,
                "inputSource": source_type
            }
            resp = requests.post(f"{self.base_url}/setInputSourceCrop", params=params, timeout=self.timeout)
            resp.raise_for_status()
            
            data = resp.json()
            if data.get("code") == 200:
                logger.info("Signal source switched to: %s", source_type)
                return True
                
            logger.error("Signal switch failed: %s", data.get("message"))
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error("Network error during signal source switch: %s", e)
            return False

    # ================================================================
    # WINDOWS & LAYOUTS
    # ================================================================

    def set_windows(self, windows: list[dict[str, int]]) -> dict[str, Any]:
        """
        Configures display windows layout.
        Endpoint: POST /setWindows
        """
        return self._post("setWindows", json_data=windows)

    def set_fullscreen_window(self) -> dict[str, Any]:
        """
        Configures a single fullscreen window matching canvas dimensions.
        """
        windows = [{
            "index": 0,
            "x": 0,
            "y": 0,
            "w": screen_config.total_width,
            "h": screen_config.total_height,
        }]
        return self.set_windows(windows)

    def get_card_info(self) -> dict[str, Any]:
        """
        Retrieves transmitting and receiving card hardware diagnostics.
        Endpoint: GET /getCardInfo
        """
        result = self._get("getCardInfo")
        return result.get("data", result)

    def get_current_windows(self) -> dict[str, Any]:
        """
        Retrieves active window configuration from device.
        Endpoint: GET /curWindows
        """
        return self._get("curWindows")

    def start_live_stream(self, stream_url: str) -> dict[str, Any]:
        """
        Initiates live stream playback (RTSP/RTMP/UDP) on the controller.
        """
        return self._get("starLive", params={"url": stream_url})

    def stop_live_stream(self) -> dict[str, Any]:
        """
        Stops live streaming on the controller.
        """
        return self._get("stopLive")
