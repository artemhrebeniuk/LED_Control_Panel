# -*- coding: utf-8 -*-
from __future__ import annotations
"""
media_utils.py — Media asset utilities and metadata probing.

Provides functions for:
- Extracting preview thumbnails (first frame) from videos and animated GIFs
- Probing media durations and frame rates via ffprobe
- Detecting animation and audio streams
"""

import json
import logging
import subprocess
from pathlib import Path

from src.core.config import VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)

# Image extensions handled via direct QPixmap loading
IMAGE_THUMBNAIL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Extensions requiring FFmpeg extraction for thumbnails
VIDEO_THUMBNAIL_EXTENSIONS = VIDEO_EXTENSIONS | {".gif"}


def get_media_duration(file_path: str) -> float:
    """
    Determines media duration (video or animated GIF) using ffprobe.

    Args:
        file_path: Path to target media file.

    Returns:
        Duration in seconds. Returns 0.0 on error or if not animated.
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
        
        # If GIF and ffprobe returns 0, assign fallback 5.0 seconds
        if dur <= 0.0 and Path(file_path).suffix.lower() == ".gif":
            return 5.0
            
        return dur

    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as e:
        logger.debug("Could not determine duration for %s: %s", file_path, e)
        return 0.0
    except FileNotFoundError:
        logger.warning("ffprobe not found in system PATH")
        return 0.0


_THUMBNAIL_CACHE: dict[str, bytes] = {}


def get_video_thumbnail_bytes(file_path: str, width: int = 64, height: int = 64) -> bytes | None:
    """
    Extracts the first frame of a video/GIF via FFmpeg and returns PNG bytes.
    Uses an in-memory cache to maintain responsive UI performance.

    Args:
        file_path: Path to media file.
        width: Maximum thumbnail width.
        height: Maximum thumbnail height.

    Returns:
        PNG image bytes, or None on failure.
    """
    cache_key = f"{file_path}_{width}x{height}"
    if cache_key in _THUMBNAIL_CACHE:
        return _THUMBNAIL_CACHE[cache_key]

    try:
        from src.core.ffmpeg_manager import get_ffmpeg_path
        result = subprocess.run(
            [
                get_ffmpeg_path(),
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
        logger.debug("Could not extract thumbnail from %s: %s", file_path, e)
        return None


def is_animated_media(file_path: str) -> bool:
    """
    Checks if media asset contains animations or video streams.

    Args:
        file_path: Target file path.

    Returns:
        True if video or multi-frame animated GIF.
    """
    ext = Path(file_path).suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        return True
    if ext == ".gif":
        duration = get_media_duration(file_path)
        return duration > 0.0
    return False


def get_media_fps(file_path: str) -> float:
    """
    Probes FPS (frames per second) of video or GIF using ffprobe.

    Args:
        file_path: Path to media file.

    Returns:
        FPS as float. Returns 0.0 on error.
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

        # Probe r_frame_rate
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
        logger.debug("Could not determine FPS for %s: %s", file_path, e)
        return 0.0
    except FileNotFoundError:
        return 0.0


def has_audio_stream(file_path: str) -> bool:
    """
    Checks whether a media asset contains an audio stream.

    Args:
        file_path: Target media file path.

    Returns:
        True if audio stream exists, False otherwise.
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
        logger.debug("Could not verify audio stream in %s: %s", file_path, e)
        return False
