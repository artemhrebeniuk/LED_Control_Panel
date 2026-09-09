from __future__ import annotations
"""
ffmpeg_manager.py — Management, detection, and retrieval of FFmpeg video engine binaries.
"""
import os
import shutil
from pathlib import Path

# Local directory for bundled FFmpeg binaries
LOCAL_TOOLS_DIR = Path("tools/ffmpeg/bin")

def get_ffmpeg_path() -> str:
    """Returns path to ffmpeg binary if found locally or in system PATH. Otherwise returns 'ffmpeg'."""
    # 1. Check local directory (priority if downloaded via app)
    local_ffmpeg = LOCAL_TOOLS_DIR / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if local_ffmpeg.exists():
        return str(local_ffmpeg.resolve())
    
    # 2. Check system PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
        
    return "ffmpeg"

def get_ffprobe_path() -> str:
    """Returns path to ffprobe binary if found locally or in system PATH. Otherwise returns 'ffprobe'."""
    local_ffprobe = LOCAL_TOOLS_DIR / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if local_ffprobe.exists():
        return str(local_ffprobe.resolve())
        
    system_ffprobe = shutil.which("ffprobe")
    if system_ffprobe:
        return system_ffprobe
        
    return "ffprobe"

def is_ffmpeg_available() -> bool:
    """Checks whether FFmpeg is available locally or in system PATH."""
    path = get_ffmpeg_path()
    if path == "ffmpeg":
        # If returned string is default 'ffmpeg', it means not found in PATH or local directory
        return False
        
    return Path(path).exists()
