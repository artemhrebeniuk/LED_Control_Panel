# -*- coding: utf-8 -*-
"""
workers.py — Рабочие потоки (QThread) для асинхронных сетевых операций.

Все сетевые вызовы к устройству Kystar KD6 выполняются в этих потоках,
чтобы основной UI-поток PyQt6 никогда не блокировался.

Архитектура потоков PyQt6:
─────────────────────────
Основной поток (Main Thread) → отвечает ТОЛЬКО за отрисовку UI.
Рабочие потоки (QThread)     → выполняют HTTP-запросы через KystarClient.

Взаимодействие потоков происходит через механизм сигналов/слотов PyQt6:
- Worker эмитит сигнал (например, finished) из рабочего потока.
- Слот в MainWindow получает сигнал и обновляет UI из основного потока.
- Это потокобезопасно благодаря очереди событий Qt (Queued Connection).
"""

import logging
import os

from PyQt6.QtCore import QThread, pyqtSignal

from src.core import config
from src.core.ffmpeg_renderer import FFmpegRenderer
from src.core.kystar_client import KystarClient, KystarClientError

logger = logging.getLogger(__name__)


class PingWorker(QThread):
    """
    Фоновый поток для периодической проверки доступности устройства.

    Каждые N миллисекунд (задаётся через config.PING_INTERVAL_MS)
    отправляет GET /device с коротким таймаутом и эмитит сигнал
    с результатом (True/False) для обновления индикатора статуса.

    Signals:
        status_changed(bool): True если устройство онлайн, False если нет.
        grid_updated(): Эмитится, когда конфигурация сетки изменилась.
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
        Основной цикл потока пинга.

        Использует QThread.msleep() вместо time.sleep() для корректной
        обработки прерывания потока при закрытии приложения.
        """
        while self._running:
            try:
                # 1. Пинг (быстрая проверка)
                is_online = self.client.ping()
                self.status_changed.emit(is_online)

                # 2. Получение данных о холсте (если онлайн)
                if is_online:
                    device_info = self.client.get_device_info()
                    screen_width = device_info.get("screenWidth", 0)
                    screen_height = device_info.get("screenHeight", 0)
                    
                    # Получаем rxNum (активные карты) для умного расчета
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
                            logger.debug("Ошибка получения brightness: %s", e)

            except Exception as e:
                logger.debug("Ошибка пинга/статуса: %s", e)
                self.status_changed.emit(False)

            # Спим между проверками (прерываемый сон)
            self.msleep(self.interval_ms)

    def stop(self) -> None:
        """Останавливает цикл пинга и ожидает завершения потока."""
        self._running = False
        self.wait(3000)  # Ждём завершения максимум 3 секунды


class UploadMediaWorker(QThread):
    """
    Поток для двухэтапной загрузки медиафайлов и запуска программы.

    Полный цикл:
    1. Для каждого файла: MD5 → checkUpload → uploadMedia (если нужно).
    2. Формирование mediaList.
    3. Отправка uploadThirdProgram.

    Signals:
        progress(int): Прогресс загрузки в процентах (0-100).
        finished(bool, str): (успех, сообщение).
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
        Загружает файлы и запускает программу.

        Прогресс-callback передаётся в KystarClient.play_media_files(),
        который вызывает его из этого же рабочего потока. Сигнал progress
        затем доставляется в основной поток через Qt Event Loop.
        """
        try:
            # Устанавливаем полноэкранное окно перед запуском
            try:
                if not self._is_aborted:
                    self.client.set_fullscreen_window()
            except Exception as e:
                logger.warning(f"Не удалось инициализировать полноэкранное окно: {e}")

            if self._is_aborted:
                self.finished.emit(False, "Загрузка отменена")
                return

            def progress_callback(p):
                if self._is_aborted:
                    # Принудительно кидаем ошибку чтобы прервать KystarClient
                    raise KystarClientError("Upload aborted by user")
                self.progress.emit(p)

            # ОПЦИОНАЛЬНАЯ АВТО-ОПТИМИЗАЦИЯ ВИДЕО
            final_file_paths = []
            if config.AUTO_OPTIMIZE_VIDEO:
                from src.core.config import VIDEO_EXTENSIONS
                renderer = FFmpegRenderer()
                for i, path in enumerate(self.file_paths):
                    if self._is_aborted:
                        raise KystarClientError("Upload aborted by user")
                    ext = os.path.splitext(path)[1].lower()
                    if ext in VIDEO_EXTENSIONS:
                        self.progress.emit(int((i / len(self.file_paths)) * 10)) # Небольшой прогресс
                        opt_path = renderer.optimize_single_video(path)
                        if opt_path:
                            final_file_paths.append(opt_path)
                        else:
                            final_file_paths.append(path) # фолбэк на оригинал
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
                    f"Программа запущена ({len(self.file_paths)} файлов)",
                )
            else:
                self.finished.emit(
                    False,
                    f"Ошибка запуска: {result.get('message', 'Неизвестная ошибка')}",
                )
        except Exception as e:
            if self._is_aborted or "Upload aborted" in str(e) or "Pool is closed" in str(e) or "aborted" in str(e):
                self.finished.emit(False, "Загрузка отменена")
            else:
                self.finished.emit(False, f"Ошибка: {e}")


class BrightnessWorker(QThread):
    """
    Поток для отправки значения яркости на устройство.

    Используется с debounce-таймером: отправляется только последнее
    значение после паузы пользователя (BRIGHTNESS_DEBOUNCE_MS).

    Signals:
        finished(bool, str): (успех, сообщение).
    """

    finished = pyqtSignal(bool, str)

    def __init__(self, client: KystarClient, value: int) -> None:
        super().__init__()
        self.client = client
        self.value = value

    def run(self) -> None:
        """Отправляет яркость и эмитит результат."""
        try:
            result = self.client.set_brightness(self.value)
            if result.get("code") == 200:
                self.finished.emit(True, f"Яркость: {self.value}%")
            else:
                self.finished.emit(
                    False,
                    f"Ошибка: {result.get('message', 'Неизвестная ошибка')}",
                )
        except KystarClientError as e:
            self.finished.emit(False, f"Ошибка: {e}")
        except Exception as e:
            self.finished.emit(False, f"Ошибка: {e}")


class ScreenPowerWorker(QThread):
    """
    Поток для включения/выключения экрана.

    Signals:
        finished(bool, str): (успех, сообщение).
    """

    finished = pyqtSignal(bool, str)

    def __init__(self, client: KystarClient, power_on: bool) -> None:
        super().__init__()
        self.client = client
        self.power_on = power_on

    def run(self) -> None:
        """Переключает состояние экрана и эмитит результат."""
        try:
            result = self.client.set_screen_power(self.power_on)
            state_text = "включён" if self.power_on else "выключен"
            if result.get("code") == 200:
                self.finished.emit(True, f"Экран {state_text}")
            else:
                self.finished.emit(
                    False,
                    f"Ошибка: {result.get('message', 'Неизвестная ошибка')}",
                )
        except KystarClientError as e:
            self.finished.emit(False, f"Ошибка: {e}")
        except Exception as e:
            self.finished.emit(False, f"Ошибка: {e}")


class RebootWorker(QThread):
    """
    Поток для перезагрузки устройства.

    Signals:
        finished(bool, str): (успех, сообщение).
    """

    finished = pyqtSignal(bool, str)

    def __init__(self, client: KystarClient) -> None:
        super().__init__()
        self.client = client

    def run(self) -> None:
        """Отправляет команду перезагрузки и эмитит результат."""
        try:
            result = self.client.reboot()
            if result.get("code") == 200:
                self.finished.emit(True, "Устройство перезагружается...")
            else:
                self.finished.emit(
                    False,
                    f"Ошибка: {result.get('message', 'Неизвестная ошибка')}",
                )
        except KystarClientError as e:
            self.finished.emit(False, f"Ошибка: {e}")
        except Exception as e:
            self.finished.emit(False, f"Ошибка: {e}")


class ClearMemoryWorker(QThread):
    """
    Фоновый поток для очистки памяти устройства.
    
    Получает список всех медиафайлов на устройстве и удаляет их по одному.
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
                self.finished.emit(True, "Память плеера уже пуста")
                return
                
            total = len(medias)
            deleted = 0
            playback_stopped = False
            
            for i, media in enumerate(medias):
                md5_and_length = media.get("md5AndLength")
                if md5_and_length:
                    success, msg = self.client.delete_media(md5_and_length)
                    
                    if not success and msg == "Файл сейчас воспроизводится" and not playback_stopped:
                        self.client.stop_playback()
                        playback_stopped = True
                        success, msg = self.client.delete_media(md5_and_length)
                        
                    if success:
                        deleted += 1
                
                # Обновляем прогресс от 10% до 100%
                p = 10 + int(((i + 1) / total) * 90)
                self.progress.emit(p)
                
            self.finished.emit(True, f"Удалено {deleted} файлов. Память очищена.")
            
        except Exception as e:
            logger.exception("Ошибка при очистке памяти")
            self.finished.emit(False, f"Ошибка: {e}")

class SwitchSourceWorker(QThread):
    """
    Фоновый поток для переключения источника сигнала (HDMI / Android).
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
                msg = "Успешно включена трансляция HDMI." if self.source_type == 3 else "Успешно возвращено к внутреннему плееру."
                self.finished.emit(True, msg)
            else:
                self.finished.emit(False, "Ошибка переключения источника сигнала. Проверьте подключение кабеля.")
        except Exception as e:
            logger.exception("Ошибка в SwitchSourceWorker:")
            self.finished.emit(False, str(e))


class FetchMediaWorker(QThread):
    """Поток для получения списка файлов с устройства и генерации превью."""
    # bool(success), list(medias), dict(md5 -> bytes of thumbnail), str(message)
    finished = pyqtSignal(bool, list, dict, str)

    def __init__(self, client, playlists_manager=None):
        super().__init__()
        self.client = client
        self.playlists_manager = playlists_manager

    def run(self):
        try:
            medias = self.client.get_all_media()
            
            # Попытка сопоставить файлы с локальными для извлечения превью
            thumbnails_map = {}
            if self.playlists_manager:
                import os
                from src.core.media_utils import get_video_thumbnail_bytes, IMAGE_THUMBNAIL_EXTENSIONS, VIDEO_THUMBNAIL_EXTENSIONS
                
                name_to_path = {}
                
                # 1. Из плейлистов
                for prog in self.playlists_manager.get_all_programs():
                    for f in prog.get("files", []):
                        if os.path.exists(f):
                            name_to_path[os.path.basename(f)] = f
                            
                # 2. Из папки rendered_scenes и temp_media (сгенерированные сцены)
                for dir_name in ["rendered_scenes", "temp_media"]:
                    if os.path.exists(dir_name):
                        try:
                            for fname in os.listdir(dir_name):
                                fpath = os.path.join(dir_name, fname)
                                if os.path.isfile(fpath):
                                    name_to_path[fname] = fpath
                        except Exception:
                            pass
                
                # Для каждого медиа на плеере пытаемся найти локальный файл по имени
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

            self.finished.emit(True, medias, thumbnails_map, "Успех")
        except Exception as e:
            self.finished.emit(False, [], {}, f"Ошибка: {e}")


class DeleteMediaWorker(QThread):
    """Поток для удаления выбранных файлов с устройства."""
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
                self.finished.emit(True, "Нет файлов для удаления")
                return
                
            deleted = 0
            errors = []
            playback_stopped = False
            
            for i, md5 in enumerate(self.md5_list):
                success, msg = self.client.delete_media(md5)
                
                # Если файл занят, пробуем остановить воспроизведение один раз и повторяем
                if not success and msg == "Файл сейчас воспроизводится" and not playback_stopped:
                    self.client.stop_playback()
                    playback_stopped = True
                    # Пробуем удалить снова
                    success, msg = self.client.delete_media(md5)
                    
                if success:
                    deleted += 1
                else:
                    errors.append(msg)
                self.progress.emit(int(((i + 1) / total) * 100))
                
            if deleted == total:
                self.finished.emit(True, f"Успешно удалено {deleted} файлов.")
            elif deleted > 0:
                self.finished.emit(True, f"Удалено {deleted} из {total} файлов.\nОшибки: {', '.join(set(errors))}")
            else:
                self.finished.emit(False, f"Не удалось удалить файлы.\nПричина: {', '.join(set(errors))}")
        except Exception as e:
            self.finished.emit(False, f"Ошибка: {e}")


import subprocess
import shutil
from PyQt6.QtGui import QImage, QPainter, QColor, QBrush
from PyQt6.QtCore import Qt

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
            
            # Генерация кадров
            temp_dir = os.path.join("temp_media", "ping_pong_frames")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Очистка старых кадров
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))
                
            self.progress.emit(10)
            
            fps = 30
            duration = 30  # 30 секунд для ожидания удара в угол
            frames = fps * duration
            
            r = min(width, height) * 0.08
            if r < 2: r = 2
            
            # Идеальный цикл для DVD-отскока (ровно в угол)
            r_log = r * 0.2
            A_x = width - 2 * r_log
            A_y = height - 2 * r_log
            
            cycles_x = 7
            cycles_y = 11
            
            img = QImage(width, height, QImage.Format.Format_RGB32)
            
            for i in range(frames):
                if self._is_aborted: return
                
                # Сдвиг на 1 кадр, чтобы удар в угол был ровно на последнем кадре видео
                t = (i + 1) / frames
                
                dist_x = t * (cycles_x * 2 * A_x)
                dist_y = t * (cycles_y * 2 * A_y)
                
                pos_x = dist_x % (2 * A_x)
                x = r_log + pos_x if pos_x < A_x else r_log + 2 * A_x - pos_x
                
                pos_y = dist_y % (2 * A_y)
                y = r_log + pos_y if pos_y < A_y else r_log + 2 * A_y - pos_y
                
                # Эффект резинового вжатия
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
                if cx - draw_w / 2 < 0: cx = draw_w / 2
                elif cx + draw_w / 2 > width: cx = width - draw_w / 2
                
                cy = y
                if cy - draw_h / 2 < 0: cy = draw_h / 2
                elif cy + draw_h / 2 > height: cy = height - draw_h / 2
                
                img.fill(QColor("black"))
                painter = QPainter(img)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setBrush(QBrush(QColor("white")))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(int(cx - draw_w / 2), int(cy - draw_h / 2), int(draw_w), int(draw_h))
                painter.end()
                
                img.save(os.path.join(temp_dir, f"frame_{i:04d}.png"))
                
                if i % 30 == 0:
                    self.progress.emit(10 + int((i / frames) * 40)) # 10 to 50%
            
            self.progress.emit(50)
            
            out_file = os.path.join("temp_media", "ping_pong.mp4")
            if os.path.exists(out_file):
                os.remove(out_file)
                
            self.progress.emit(60)
            
            # Сборка видео через FFmpeg
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
            
            if self._is_aborted: return
            
            # Отправка на плеер
            def upload_prog(pct):
                self.progress.emit(80 + int(pct * 0.2)) # 80 to 100%
                
            md5_len = self.client.upload_media(out_file, progress_callback=upload_prog)
            media_item = {
                "md5AndLength": md5_len,
                "duration": 0,
                "anim": "NONE"
            }
            res = self.client.upload_third_program([media_item], "Ping Pong")
            
            if res.get("code") == 200:
                self.finished.emit(True, "Пинг-Понг запущен!")
            else:
                self.finished.emit(False, f"Ошибка: {res.get('message', '')}")
                
        except Exception as e:
            self.finished.emit(False, str(e))
            
    def abort(self):
        self._is_aborted = True
