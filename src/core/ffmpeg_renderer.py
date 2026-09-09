# -*- coding: utf-8 -*-
from __future__ import annotations
"""
ffmpeg_renderer.py — Multi-zone scene compositing and video processing via FFmpeg.

Supported media:
- Images (jpg, png, bmp, webp)
- Video (mp4, avi, mkv, mov, etc.)
- Animated GIFs
- Mixed scenes (video and static images in separate zones)

Key Architectural Solutions:
1. Short videos / static image persistence:
   Instead of `shortest=1` in overlay (which prematurely terminates the render
   after 1 frame if static images are present), we use `eof_action=pass`.
   When a shorter video or GIF ends, its final frame freezes in place,
   allowing longer videos to complete their full duration.
2. Timestamp synchronization:
   When combining media with varying frame rates, timestamps are normalized
   using `setpts=PTS-STARTPTS` and aligned to a uniform `fps={target}`.
3. Hardware FPS Capping:
   LED hardware cannot process 60 FPS video decodes reliably. Final output
   is strictly capped at 30 FPS (`_MAX_OUTPUT_FPS`) to prevent decoder overruns.
"""

import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from src.core import config
from src.core.media_utils import get_media_duration, get_media_fps, has_audio_stream

logger = logging.getLogger(__name__)

# Extensions treated as video streams by FFmpeg
_VIDEO_LIKE_EXTENSIONS = config.VIDEO_EXTENSIONS | {".gif"}

# Maximum output FPS (prevent hardware decoder overload on Kystar KD6)
_MAX_OUTPUT_FPS = 30
_DEFAULT_FPS = 25


class FFmpegRenderer:
    """Multi-zone scene compositing engine utilizing FFmpeg."""
    
    def __init__(self, output_dir: str = "rendered_scenes"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def _cleanup_old_scenes(self, max_files: int = 5):
        """
        Cleans up older generated scene files, keeping only `max_files` newest
        to conserve local disk space.
        """
        try:
            if not self.output_dir.exists():
                return
            
            # Sort files by modification time (oldest first)
            files = sorted(
                self.output_dir.iterdir(),
                key=lambda p: p.stat().st_mtime
            )
            
            files_to_delete = files[:-max_files] if len(files) > max_files else []
            
            for file_path in files_to_delete:
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        logger.debug("Cleaned up old scene file: %s", file_path)
                    except Exception as e:
                        logger.warning("Could not delete old scene file %s: %s", file_path, e)
                        
        except Exception as e:
            logger.error("Error during scene cleanup: %s", e)
        
    def render_scene(self, zones: list[dict], rows: int, cols: int) -> str:
        """
        Composites multi-zone layout into a single output file.
        
        If video or GIF is present, renders an MP4 video matching the duration of the longest track.
        If only static images are provided, renders a single PNG image.
        
        Args:
            zones: List of zone dictionaries with keys: row, col, rowSpan, colSpan, media.
            rows: Number of grid rows.
            cols: Number of grid columns.
            
        Returns:
            str: Path to output media file (mp4 or png). Returns empty string on failure.
        """
        self._cleanup_old_scenes()
        
        if not zones:
            return ""

        panel_w = config.PANEL_WIDTH
        panel_h = config.PANEL_HEIGHT
        
        safe_w = max(1, cols * panel_w)
        safe_h = max(1, rows * panel_h)
        
        # Check if any zone contains video or animated GIF
        has_video = any(
            Path(z["media"]).suffix.lower() in _VIDEO_LIKE_EXTENSIONS 
            for z in zones
        )
        
        max_duration = 0.0
        target_fps = _DEFAULT_FPS
        
        if has_video:
            fps_values = []
            audio_inputs = []
            for i, z in enumerate(zones):
                ext = Path(z["media"]).suffix.lower()
                if ext in _VIDEO_LIKE_EXTENSIONS:
                    dur = get_media_duration(z["media"])
                    if dur > max_duration:
                        max_duration = dur
                    
                    fps = get_media_fps(z["media"])
                    if fps > 0:
                        fps_values.append(fps)
                        
                    if has_audio_stream(z["media"]):
                        audio_inputs.append(i)
            
            # Target FPS: highest source FPS, capped at _MAX_OUTPUT_FPS
            if fps_values:
                target_fps = min(max(fps_values), _MAX_OUTPUT_FPS)
            
            if max_duration <= 0:
                max_duration = 15.0
                
            logger.info(
                "Video scene: duration=%.1f s, FPS=%.1f", 
                max_duration, target_fps
            )
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = ".mp4" if has_video else ".png"
        output_file = str(self.output_dir / f"scene_{timestamp}{ext}")
        
        from src.core.ffmpeg_manager import get_ffmpeg_path
        cmd = [get_ffmpeg_path(), "-y"]
        
        # Add input streams
        for z in zones:
            media = str(z["media"])
            media_ext = Path(media).suffix.lower()
            
            if media_ext in _VIDEO_LIKE_EXTENSIONS:
                if media_ext == ".gif":
                    cmd.extend(["-ignore_loop", "0"])
            else:
                if has_video:
                    cmd.extend(["-loop", "1", "-framerate", str(int(target_fps))])
                    
            cmd.extend(["-i", media])
            
        # Build filter_complex
        filters = []
        
        # Solid black canvas background
        if has_video:
            filters.append(
                f"color=c=black:s={safe_w}x{safe_h}"
                f":d={max_duration}:r={int(target_fps)}[bg]"
            )
        else:
            filters.append(f"color=c=black:s={safe_w}x{safe_h}[bg]")
        
        # Scale and normalize frame rates for inputs
        for i, z in enumerate(zones):
            target_w = z["colSpan"] * panel_w
            target_h = z["rowSpan"] * panel_h
            
            if has_video:
                filters.append(
                    f"[{i}:v]fps={int(target_fps)},"
                    f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                    f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black@0,"
                    f"setpts=PTS-STARTPTS[v{i}]"
                )
            else:
                filters.append(
                    f"[{i}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                    f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black@0[v{i}]"
                )
            
        # Overlay zones on top of background
        prev_bg = "bg"
        for i, z in enumerate(zones):
            x = z["col"] * panel_w
            y = z["row"] * panel_h
            out_name = f"out{i}" if i < len(zones) - 1 else "final_out"
            
            if has_video:
                filters.append(
                    f"[{prev_bg}][v{i}]overlay=x={x}:y={y}:format=rgb"
                    f":eof_action=pass[{out_name}]"
                )
            else:
                filters.append(
                    f"[{prev_bg}][v{i}]overlay=x={x}:y={y}:format=rgb[{out_name}]"
                )
            prev_bg = out_name
            
        if has_video:
            # Color matrix processing
            if config.CRUSH_BLACKS:
                filters.append(
                    "[final_out]colorlevels=rimin=0.05:gimin=0.05:bimin=0.05,"
                    "scale=out_color_matrix=bt709:out_range=pc[color_out]"
                )
            else:
                filters.append(
                    "[final_out]scale=out_color_matrix=bt709:out_range=pc[color_out]"
                )
            
        if has_video and audio_inputs:
            amix_inputs = "".join([f"[{i}:a]" for i in audio_inputs])
            filters.append(f"{amix_inputs}amix=inputs={len(audio_inputs)}:duration=longest[a_out]")
            
        filter_str = ";".join(filters)
        cmd.extend(["-filter_complex", filter_str])
        
        if has_video:
            cmd.extend(["-map", "[color_out]"])
            if audio_inputs:
                cmd.extend(["-map", "[a_out]", "-c:a", "aac"])
            cmd.extend(["-t", f"{max_duration:.2f}"])
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-r", str(int(target_fps)),
                "-movflags", "+faststart",
                "-color_primaries", "bt709",
                "-color_trc", "bt709",
                "-colorspace", "bt709",
                "-color_range", "pc"
            ])
            
            if config.LIMIT_BITRATE:
                cmd.extend([
                    "-maxrate", "4M",
                    "-bufsize", "8M",
                    "-g", str(int(target_fps))
                ])
        else:
            cmd.extend(["-map", "[final_out]"])
            cmd.extend(["-vframes", "1"])
            
        cmd.append(output_file)
        
        logger.info("Executing FFmpeg command: %s", " ".join(cmd))
        
        process = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            encoding="utf-8", 
            errors="replace"
        )
        
        if process.returncode != 0:
            logger.error("FFmpeg Error: %s", process.stderr)
            raise RuntimeError(f"FFmpeg failed with code {process.returncode}")
            
        return output_file

    def optimize_single_video(self, input_path: str) -> str:
        """
        Optimizes a single video file to match hardware LED dimensions.
        Applies configured optimizations (FPS limit, color range, letterboxing).
        """
        self._cleanup_old_scenes()
        
        target_w = config.SCREEN_COLS * config.PANEL_WIDTH
        target_h = config.SCREEN_ROWS * config.PANEL_HEIGHT
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = str(self.output_dir / f"opt_{timestamp}.mp4")
        
        from src.core.ffmpeg_manager import get_ffmpeg_path
        cmd = [get_ffmpeg_path(), "-y", "-i", input_path]
        
        fps = get_media_fps(input_path)
        target_fps = min(fps if fps > 0 else _DEFAULT_FPS, _MAX_OUTPUT_FPS)
        
        fc_list = [
            f"color=c=black:s={target_w}x{target_h}[bg]",
            f"[0:v]fps={int(target_fps)},scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[fg]",
            f"[bg][fg]overlay=x='(W-w)/2':y='(H-h)/2':format=rgb:shortest=1[out]"
        ]
        
        color_matrix = "scale=out_color_matrix=bt709:out_range=pc"
        if config.CRUSH_BLACKS:
            fc_list.append(f"[out]colorlevels=rimin=0.05:gimin=0.05:bimin=0.05,{color_matrix}[color_out]")
        else:
            fc_list.append(f"[out]{color_matrix}[color_out]")
            
        filter_str = ";".join(fc_list)
        cmd.extend(["-filter_complex", filter_str, "-map", "[color_out]"])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-r", str(int(target_fps)),
            "-movflags", "+faststart",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-colorspace", "bt709",
            "-color_range", "pc"
        ])
        
        if config.LIMIT_BITRATE:
            cmd.extend([
                "-maxrate", "4M",
                "-bufsize", "8M",
                "-g", str(int(target_fps))
            ])
            
        if has_audio_stream(input_path):
            cmd.extend(["-c:a", "aac"])
        else:
            cmd.extend(["-an"])
            
        cmd.append(output_file)
            
        try:
            logger.info("Executing FFmpeg single video optimization: %s", input_path)
            kwargs = {}
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            subprocess.run(cmd, check=True, **kwargs)
            logger.info("Video successfully optimized: %s", output_file)
            return output_file
        except subprocess.CalledProcessError as e:
            logger.error("FFmpeg optimization error: %s", e)
            return ""
