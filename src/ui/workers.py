# -*- coding: utf-8 -*-
from __future__ import annotations
"""
workers.py — Worker threads (QThread) for asynchronous network operations.

All network calls to the Kystar KD6 device are executed in these threads
so that the main PyQt6 UI thread is never blocked.

PyQt6 Thread Architecture:
─────────────────────────
Main Thread   → Responsible ONLY for rendering the UI.
Worker Threads (QThread) → Execute HTTP requests via KystarClient.

Thread communication occurs via PyQt6 signals and slots:
- Worker emits a signal (e.g., finished) from the worker thread.
- Slot in MainWindow receives the signal and updates the UI from the main thread.
- This is thread-safe thanks to Qt's event loop (Queued Connection).
"""

import logging
import os
import shutil
import subprocess

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter

from src.core import config
from src.core.ffmpeg_renderer import FFmpegRenderer
from src.core.kystar_client import KystarClient, KystarClientError

logger = logging.getLogger(__name__)


class PingWorker(QThread):
    """
    Background worker thread for periodic device availability checks.

    Sends GET /device with a short timeout every N milliseconds
    (defined by config.PING_INTERVAL_MS) and emits a signal with
    the result (True/False) to update the status indicator.

    Signals:
        status_changed(bool): True if device is online, False otherwise.
        grid_updated(): Emitted when the grid configuration changes.
        brightness_received(int): Emitted with current brightness value on first ping.
    """

    status_changed = pyqtSignal(bool)
    grid_updated = pyqtSignal()
    brightness_received = pyqtSignal(int)

    def __init__(self, client: KystarClient, interval_ms: int = 5000) -> None:
        super().__init__()
        self.client = client
        self.interval_ms = interval_ms
        self._running = True
        self._first_ping_done = False

    def run(self) -> None:
        """
        Main ping worker loop.

        Uses QThread.msleep() instead of time.sleep() for responsive
        thread interruption when closing the application.
        """
        while self._running:
            try:
                # 1. Ping (fast check)
                is_online = self.client.ping()
                self.status_changed.emit(is_online)

                # 2. Retrieve canvas info if online
                if is_online:
                    device_info = self.client.get_device_info()
                    screen_width = device_info.get("screenWidth", 0)
                    screen_height = device_info.get("screenHeight", 0)

                    # Retrieve rxNum (active receiving cards) for smart calculation
                    try:
                        card_info = self.client.get_card_info()
                        rx_num = card_info.get("rxNum", 0)
                    except Exception:
                        rx_num = 0

                    from src.core.config import screen_config
                    if screen_config.update_from_device_info(screen_width, screen_height, rx_num):
                        self.grid_updated.emit()

                    if not self._first_ping_done:
                        try:
                            screen_params = self.client.get_screen_params()
                            if "bright" in screen_params:
                                self.brightness_received.emit(int(screen_params["bright"]))
                            self._first_ping_done = True
                        except Exception as e:
                            logger.debug("Error retrieving brightness: %s", e)

            except Exception as e:
                logger.debug("Ping/status check error: %s", e)
                self.status_changed.emit(False)

            # Interruptible sleep between checks
            self.msleep(self.interval_ms)

    def stop(self) -> None:
        """Stops the ping loop and waits for thread completion."""
        self._running = False
        self.wait(3000)


class UploadMediaWorker(QThread):
    """
    Worker thread for two-stage media upload and program execution.

    Full cycle:
    1. For each file: MD5 -> checkUpload -> uploadMedia (if needed).
    2. Build mediaList.
    3. Send uploadThirdProgram.

    Signals:
        progress(int): Upload progress percentage (0-100).
        finished(bool, str): (success, message).
    """

    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, client: KystarClient, file_paths: list[str], image_duration_sec: int = 10) -> None:
        super().__init__()
        self.client = client
        self.file_paths = file_paths
        self.image_duration_sec = image_duration_sec
        self._is_aborted = False

    def run(self) -> None:
        """
        Uploads files and starts playback.

        Progress callback is forwarded to KystarClient.play_media_files(),
        which invokes it from this worker thread. The progress signal is
        delivered to the main thread via the Qt Event Loop.
        """
        try:
            # Set fullscreen window before start
            try:
                if not self._is_aborted:
                    self.client.set_fullscreen_window()
            except Exception as e:
                logger.warning(f"Failed to initialize fullscreen window: {e}")

            if self._is_aborted:
                self.finished.emit(False, "Upload cancelled")
                return

            def progress_callback(p):
                if self._is_aborted:
                    raise KystarClientError("Upload aborted by user")
                self.progress.emit(p)

            # Optional video auto-optimization
            final_file_paths = []
            if config.AUTO_OPTIMIZE_VIDEO:
                from src.core.config import VIDEO_EXTENSIONS
                renderer = FFmpegRenderer()
                for i, path in enumerate(self.file_paths):
                    if self._is_aborted:
                        raise KystarClientError("Upload aborted by user")
                    ext = os.path.splitext(path)[1].lower()
                    if ext in VIDEO_EXTENSIONS:
                        self.progress.emit(int((i / len(self.file_paths)) * 10))
                        opt_path = renderer.optimize_single_video(path)
                        if opt_path:
                            final_file_paths.append(opt_path)
                        else:
                            final_file_paths.append(path)
                    else:
                        final_file_paths.append(path)
            else:
                final_file_paths = self.file_paths

            result = self.client.play_media_files(
                file_paths=final_file_paths,
                image_duration_sec=self.image_duration_sec,
                progress_callback=progress_callback,
            )
            if result.get("code") == 200:
                self.finished.emit(
                    True,
                    f"Program launched ({len(self.file_paths)} files)",
                )
            else:
                self.finished.emit(
                    False,
                    f"Launch error: {result.get('message', 'Unknown error')}",
                )
        except Exception as e:
            if self._is_aborted or "Upload aborted" in str(e) or "Pool is closed" in str(e) or "aborted" in str(e):
                self.finished.emit(False, "Upload cancelled")
            else:
                self.finished.emit(False, f"Error: {e}")


class BrightnessWorker(QThread):
    """
    Worker thread to send brightness level to device.

    Used with debounce timer: sends only the latest value
    after user stops adjusting (BRIGHTNESS_DEBOUNCE_MS).

    Signals:
        finished(bool, str): (success, message).
    """

    finished = pyqtSignal(bool, str)

    def __init__(self, client: KystarClient, value: int) -> None:
        super().__init__()
        self.client = client
        self.value = value

    def run(self) -> None:
        """Sends brightness value and emits result."""
        try:
            result = self.client.set_brightness(self.value)
            if result.get("code") == 200:
                self.finished.emit(True, f"Brightness: {self.value}%")
            else:
                self.finished.emit(
                    False,
                    f"Error: {result.get('message', 'Unknown error')}",
                )
        except KystarClientError as e:
            self.finished.emit(False, f"Error: {e}")
        except Exception as e:
            self.finished.emit(False, f"Error: {e}")


class ScreenPowerWorker(QThread):
    """
    Worker thread to toggle screen power on/off.

    Signals:
        finished(bool, str): (success, message).
    """

    finished = pyqtSignal(bool, str)

    def __init__(self, client: KystarClient, power_on: bool) -> None:
        super().__init__()
        self.client = client
        self.power_on = power_on

    def run(self) -> None:
        """Toggles screen state and emits result."""
        try:
            result = self.client.set_screen_power(self.power_on)
            state_text = "ON" if self.power_on else "OFF"
            if result.get("code") == 200:
                self.finished.emit(True, f"Screen power: {state_text}")
            else:
                self.finished.emit(
                    False,
                    f"Error: {result.get('message', 'Unknown error')}",
                )
        except KystarClientError as e:
            self.finished.emit(False, f"Error: {e}")
        except Exception as e:
            self.finished.emit(False, f"Error: {e}")


class RebootWorker(QThread):
    """
    Worker thread to reboot the device.

    Signals:
        finished(bool, str): (success, message).
    """

    finished = pyqtSignal(bool, str)

    def __init__(self, client: KystarClient) -> None:
        super().__init__()
        self.client = client

    def run(self) -> None:
        """Sends reboot command and emits result."""
        try:
            result = self.client.reboot()
            if result.get("code") == 200:
                self.finished.emit(True, "Device is rebooting...")
            else:
                self.finished.emit(
                    False,
                    f"Error: {result.get('message', 'Unknown error')}",
                )
        except KystarClientError as e:
            self.finished.emit(False, f"Error: {e}")
        except Exception as e:
            self.finished.emit(False, f"Error: {e}")


class ClearMemoryWorker(QThread):
    """
    Background worker thread to clear device media storage.

    Retrieves all media files on device and deletes them one by one.
    """
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, client: KystarClient) -> None:
        super().__init__()
        self.client = client

    def run(self) -> None:
        try:
            self.progress.emit(10)
            medias = self.client.get_all_media()
            if not medias:
                self.progress.emit(100)
                self.finished.emit(True, "Player memory is already empty")
                return

            total = len(medias)
            deleted = 0
            playback_stopped = False

            for i, media in enumerate(medias):
                md5_and_length = media.get("md5AndLength")
                if md5_and_length:
                    success, msg = self.client.delete_media(md5_and_length)

                    if not success and ("playback" in msg.lower() or "playing" in msg.lower()) and not playback_stopped:
                        self.client.stop_playback()
                        playback_stopped = True
                        success, msg = self.client.delete_media(md5_and_length)

                    if success:
                        deleted += 1

                p = 10 + int(((i + 1) / total) * 90)
                self.progress.emit(p)

            self.finished.emit(True, f"Deleted {deleted} files. Storage cleared.")

        except Exception as e:
            logger.exception("Error clearing memory")
            self.finished.emit(False, f"Error: {e}")


class SwitchSourceWorker(QThread):
    """
    Background worker thread to switch input source (HDMI / Android internal player).
    """

    finished = pyqtSignal(bool, str)

    def __init__(self, client: KystarClient, source_type: int, width: int = 1920, height: int = 1080) -> None:
        super().__init__()
        self.client = client
        self.source_type = source_type
        self.width = width
        self.height = height

    def run(self) -> None:
        try:
            success = self.client.set_input_source(self.source_type, self.width, self.height)
            if success:
                msg = "HDMI input broadcast activated." if self.source_type == 3 else "Switched back to internal media player."
                self.finished.emit(True, msg)
            else:
                self.finished.emit(False, "Error switching input source. Please check cable connection.")
        except Exception as e:
            logger.exception("Error in SwitchSourceWorker:")
            self.finished.emit(False, str(e))


class FetchMediaWorker(QThread):
    """Worker thread to fetch media list from device and generate thumbnails."""
    # bool(success), list(medias), dict(md5 -> bytes of thumbnail), str(message)
    finished = pyqtSignal(bool, list, dict, str)

    def __init__(self, client, playlists_manager=None):
        super().__init__()
        self.client = client
        self.playlists_manager = playlists_manager

    def run(self):
        try:
            medias = self.client.get_all_media()

            # Attempt to match files with local files to extract thumbnails
            thumbnails_map = {}
            if self.playlists_manager:
                from src.core.media_utils import IMAGE_THUMBNAIL_EXTENSIONS, VIDEO_THUMBNAIL_EXTENSIONS, get_video_thumbnail_bytes

                name_to_path = {}

                # 1. From playlists
                for prog in self.playlists_manager.get_all_programs():
                    for f in prog.get("files", []):
                        if os.path.exists(f):
                            name_to_path[os.path.basename(f)] = f

                # 2. From rendered_scenes and temp_media folders
                for dir_name in ["rendered_scenes", "temp_media"]:
                    if os.path.exists(dir_name):
                        try:
                            for fname in os.listdir(dir_name):
                                fpath = os.path.join(dir_name, fname)
                                if os.path.isfile(fpath):
                                    name_to_path[fname] = fpath
                        except Exception:
                            pass

                # Match device media by name
                for media in medias:
                    md5 = media.get("md5AndLength")
                    name = media.get("name")

                    if name in name_to_path:
                        local_path = name_to_path[name]
                        ext = os.path.splitext(local_path)[1].lower()
                        thumb_bytes = None

                        try:
                            if ext in VIDEO_THUMBNAIL_EXTENSIONS or ext == ".gif":
                                thumb_bytes = get_video_thumbnail_bytes(local_path, width=48, height=48)
                            elif ext in IMAGE_THUMBNAIL_EXTENSIONS:
                                with open(local_path, "rb") as f:
                                    thumb_bytes = f.read()
                        except Exception:
                            pass

                        if thumb_bytes:
                            thumbnails_map[md5] = thumb_bytes

            self.finished.emit(True, medias, thumbnails_map, "Success")
        except Exception as e:
            self.finished.emit(False, [], {}, f"Error: {e}")


class DeleteMediaWorker(QThread):
    """Worker thread to delete selected files from device."""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, client, md5_list):
        super().__init__()
        self.client = client
        self.md5_list = md5_list

    def run(self):
        try:
            total = len(self.md5_list)
            if total == 0:
                self.finished.emit(True, "No files to delete")
                return

            deleted = 0
            errors = []
            playback_stopped = False

            for i, md5 in enumerate(self.md5_list):
                success, msg = self.client.delete_media(md5)

                # If file is busy, stop playback once and retry
                if not success and ("playback" in msg.lower() or "playing" in msg.lower()) and not playback_stopped:
                    self.client.stop_playback()
                    playback_stopped = True
                    success, msg = self.client.delete_media(md5)

                if success:
                    deleted += 1
                else:
                    errors.append(msg)
                self.progress.emit(int(((i + 1) / total) * 100))

            if deleted == total:
                self.finished.emit(True, f"Successfully deleted {deleted} files.")
            elif deleted > 0:
                self.finished.emit(True, f"Deleted {deleted} of {total} files.\nErrors: {', '.join(set(errors))}")
            else:
                self.finished.emit(False, f"Failed to delete files.\nReason: {', '.join(set(errors))}")
        except Exception as e:
            self.finished.emit(False, f"Error: {e}")


class PingPongWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, client):
        super().__init__()
        self.client = client
        self._is_aborted = False

    def run(self) -> None:
        try:
            self.progress.emit(5)
            from src.core.config import screen_config
            width = screen_config.total_width
            height = screen_config.total_height

            # Frame generation
            temp_dir = os.path.join("temp_media", "ping_pong_frames")
            os.makedirs(temp_dir, exist_ok=True)

            # Clear old frames
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))

            self.progress.emit(10)

            fps = 30
            duration = 30  # 30 seconds to hit the corner
            frames = fps * duration

            r = min(width, height) * 0.08
            if r < 2:
                r = 2

            # DVD bounce loop hitting corner on the final frame
            r_log = r * 0.2
            A_x = width - 2 * r_log
            A_y = height - 2 * r_log

            cycles_x = 7
            cycles_y = 11

            img = QImage(width, height, QImage.Format.Format_RGB32)

            for i in range(frames):
                if self._is_aborted:
                    return

                t = (i + 1) / frames

                dist_x = t * (cycles_x * 2 * A_x)
                dist_y = t * (cycles_y * 2 * A_y)

                pos_x = dist_x % (2 * A_x)
                x = r_log + pos_x if pos_x < A_x else r_log + 2 * A_x - pos_x

                pos_y = dist_y % (2 * A_y)
                y = r_log + pos_y if pos_y < A_y else r_log + 2 * A_y - pos_y

                # Rubber squash/stretch effect
                factor_x = 1.0
                if x < r:
                    factor_x = 0.5 + 0.5 * (x - r_log) / (r - r_log)
                elif x > width - r:
                    factor_x = 0.5 + 0.5 * ((width - x) - r_log) / (r - r_log)

                factor_y = 1.0
                if y < r:
                    factor_y = 0.5 + 0.5 * (y - r_log) / (r - r_log)
                elif y > height - r:
                    factor_y = 0.5 + 0.5 * ((height - y) - r_log) / (r - r_log)

                expand_x = 1.0 + (1.0 - factor_y)
                expand_y = 1.0 + (1.0 - factor_x)

                draw_w = 2 * r * factor_x * expand_x
                draw_h = 2 * r * factor_y * expand_y

                cx = x
                if cx - draw_w / 2 < 0:
                    cx = draw_w / 2
                elif cx + draw_w / 2 > width:
                    cx = width - draw_w / 2

                cy = y
                if cy - draw_h / 2 < 0:
                    cy = draw_h / 2
                elif cy + draw_h / 2 > height:
                    cy = height - draw_h / 2

                img.fill(QColor("black"))
                painter = QPainter(img)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setBrush(QBrush(QColor("white")))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(int(cx - draw_w / 2), int(cy - draw_h / 2), int(draw_w), int(draw_h))
                painter.end()

                img.save(os.path.join(temp_dir, f"frame_{i:04d}.png"))

                if i % 30 == 0:
                    self.progress.emit(10 + int((i / frames) * 40))

            self.progress.emit(50)

            out_file = os.path.join("temp_media", "ping_pong.mp4")
            if os.path.exists(out_file):
                os.remove(out_file)

            self.progress.emit(60)

            # Assemble video via FFmpeg
            ffmpeg_path = os.environ.get("FFMPEG_PATH", "ffmpeg")
            cmd = [
                ffmpeg_path, "-y",
                "-framerate", str(fps),
                "-i", os.path.join(temp_dir, "frame_%04d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "18",
                out_file
            ]

            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            self.progress.emit(80)

            if self._is_aborted:
                return

            # Deploy to player
            def upload_prog(pct):
                self.progress.emit(80 + int(pct * 0.2))

            md5_len = self.client.upload_media(out_file, progress_callback=upload_prog)
            media_item = {
                "md5AndLength": md5_len,
                "duration": 0,
                "anim": "NONE"
            }
            res = self.client.upload_third_program([media_item], "Ping Pong")

            if res.get("code") == 200:
                self.finished.emit(True, "Ping Pong launched successfully!")
            else:
                self.finished.emit(False, f"Error: {res.get('message', '')}")

        except Exception as e:
            self.finished.emit(False, str(e))

    def abort(self):
        self._is_aborted = True
