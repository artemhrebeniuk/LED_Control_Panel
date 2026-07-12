# -*- coding: utf-8 -*-
"""
media_utils.py — Утилиты для работы с медиафайлами.

Предоставляет функции для:
- Извлечения превью (первый кадр) из видео и GIF
- Определения длительности медиафайлов
- Проверки, является ли файл анимированным
"""

import json
import logging
import subprocess
from pathlib import Path

from src.core.config import VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)

# Расширения, для которых мы создаём миниатюры как для изображений (через QPixmap)
IMAGE_THUMBNAIL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Расширения, для которых мы извлекаем первый кадр через FFmpeg
VIDEO_THUMBNAIL_EXTENSIONS = VIDEO_EXTENSIONS | {".gif"}


def get_media_duration(file_path: str) -> float:
    """
    Определяет длительность медиафайла (видео или анимированный GIF) через ffprobe.

    Args:
        file_path: Путь к медиафайлу.

    Returns:
        Длительность в секундах. Возвращает 0.0 при ошибке или
        если файл не является видео/анимацией.
    """
    try:
        from src.core.ffmpeg_manager import get_ffprobe_path
        result = subprocess.run(
            [
                get_ffprobe_path(),
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(file_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )

        if result.returncode != 0:
            return 0.0

        data = json.loads(result.stdout)
        duration_str = data.get("format", {}).get("duration", "0")
        dur = float(duration_str)
        
        # Если это GIF и ffprobe не вернул длительность, ставим искусственные 5 секунд
        if dur <= 0.0 and Path(file_path).suffix.lower() == ".gif":
            return 5.0
            
        return dur

    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as e:
        logger.debug("Не удалось определить длительность %s: %s", file_path, e)
        return 0.0
    except FileNotFoundError:
        logger.warning("ffprobe не найден в PATH")
        return 0.0


_THUMBNAIL_CACHE: dict[str, bytes] = {}


def get_video_thumbnail_bytes(file_path: str, width: int = 64, height: int = 64) -> bytes | None:
    """
    Извлекает первый кадр из видео/GIF через FFmpeg и возвращает PNG-данные.
    Использует кэширование для ускорения работы UI.

    Args:
        file_path: Путь к видео или GIF файлу.
        width: Максимальная ширина превью.
        height: Максимальная высота превью.

    Returns:
        Байты PNG-изображения или None при ошибке.
    """
    cache_key = f"{file_path}_{width}x{height}"
    if cache_key in _THUMBNAIL_CACHE:
        return _THUMBNAIL_CACHE[cache_key]

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", str(file_path),
                "-vframes", "1",
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease",
                "-f", "image2pipe",
                "-vcodec", "png",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout:
            _THUMBNAIL_CACHE[cache_key] = result.stdout
            return result.stdout

        return None

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.debug("Не удалось извлечь превью из %s: %s", file_path, e)
        return None


def is_animated_media(file_path: str) -> bool:
    """
    Проверяет, является ли файл анимированным медиа (видео или анимированный GIF).

    Args:
        file_path: Путь к файлу.

    Returns:
        True если файл содержит анимацию/видеопоток.
    """
    ext = Path(file_path).suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        return True
    if ext == ".gif":
        # Проверяем, есть ли в GIF больше одного кадра
        duration = get_media_duration(file_path)
        return duration > 0.0
    return False


def get_media_fps(file_path: str) -> float:
    """
    Определяет FPS (кадров в секунду) видео/GIF через ffprobe.

    Args:
        file_path: Путь к медиафайлу.

    Returns:
        FPS как float. Возвращает 0.0 при ошибке.
    """
    try:
        from src.core.ffmpeg_manager import get_ffprobe_path
        result = subprocess.run(
            [
                get_ffprobe_path(),
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "v:0",
                str(file_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )

        if result.returncode != 0:
            return 0.0

        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if not streams:
            return 0.0

        stream = streams[0]

        # Пробуем r_frame_rate (реальный FPS)
        r_frame_rate = stream.get("r_frame_rate", "0/1")
        if "/" in r_frame_rate:
            num, den = r_frame_rate.split("/")
            num, den = int(num), int(den)
            if den > 0:
                fps = num / den
                if 1.0 <= fps <= 120.0:
                    return fps

        # Fallback: avg_frame_rate
        avg_frame_rate = stream.get("avg_frame_rate", "0/1")
        if "/" in avg_frame_rate:
            num, den = avg_frame_rate.split("/")
            num, den = int(num), int(den)
            if den > 0:
                fps = num / den
                if 1.0 <= fps <= 120.0:
                    return fps

        return 0.0

    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError, ZeroDivisionError) as e:
        logger.debug("Не удалось определить FPS %s: %s", file_path, e)
        return 0.0
    except FileNotFoundError:
        return 0.0

def has_audio_stream(file_path: str) -> bool:
    """
    Проверяет, есть ли в медиафайле аудиодорожка.

    Args:
        file_path: Путь к медиафайлу.

    Returns:
        True если аудиодорожка найдена, False иначе.
    """
    try:
        from src.core.ffmpeg_manager import get_ffprobe_path
        result = subprocess.run(
            [
                get_ffprobe_path(),
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "a",
                str(file_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )

        if result.returncode != 0:
            return False

        data = json.loads(result.stdout)
        return len(data.get("streams", [])) > 0

    except Exception as e:
        logger.debug("Не удалось проверить аудио в %s: %s", file_path, e)
        return False

