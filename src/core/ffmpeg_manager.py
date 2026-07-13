"""
Управление загрузкой и поиском видеодвижка FFmpeg.
"""
import os
import shutil
from pathlib import Path

# Локальная директория для хранения FFmpeg
LOCAL_TOOLS_DIR = Path("tools/ffmpeg/bin")

def get_ffmpeg_path() -> str:
    """Возвращает путь к ffmpeg, если он найден локально или в PATH. Иначе возвращает 'ffmpeg'."""
    # 1. Проверяем локальную директорию (имеет приоритет, если мы сами скачали)
    local_ffmpeg = LOCAL_TOOLS_DIR / "ffmpeg.exe"
    if local_ffmpeg.exists():
        return str(local_ffmpeg.resolve())
    
    # 2. Проверяем системный PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
        
    return "ffmpeg"

def get_ffprobe_path() -> str:
    """Возвращает путь к ffprobe, аналогично get_ffmpeg_path()."""
    local_ffprobe = LOCAL_TOOLS_DIR / "ffprobe.exe"
    if local_ffprobe.exists():
        return str(local_ffprobe.resolve())
        
    system_ffprobe = shutil.which("ffprobe")
    if system_ffprobe:
        return system_ffprobe
        
    return "ffprobe"

def is_ffmpeg_available() -> bool:
    """Проверяет доступность ffmpeg в системе или локально."""
    # Если get_ffmpeg_path() вернул валидный путь с существующим файлом
    path = get_ffmpeg_path()
    
    # shutil.which возвращает None если не найдено, а get_ffmpeg_path может вернуть 'ffmpeg'
    if path == "ffmpeg":
        # Если returned string is exactly 'ffmpeg', it means it wasn't found in PATH and local file doesn't exist
        return False
        
    return Path(path).exists()
