# -*- coding: utf-8 -*-
"""
ffmpeg_renderer.py — Сборка многозонных сцен через FFmpeg.

Поддерживает:
- Изображения (jpg, png, bmp, webp)
- Видео (mp4, avi, mkv, mov и др.)
- Анимированные GIF
- Смешанные сцены (видео + картинки в разных зонах)

ПОДВОДНЫЕ КАМНИ И РЕШЕНИЯ (Важно для будущей разработки):
1. Проблема коротких видео/картинок: Если использовать `shortest=1` в overlay, 
   любая статичная картинка моментально завершит рендер (1 кадр). 
   Решение: используем `eof_action=pass` — когда короткое видео или GIF заканчивается, 
   оно замирает на последнем кадре, позволяя длинному видео доиграть до конца.
2. Рассинхронизация времени: При объединении видео с разными FPS, overlay ломается.
   Решение: Использование `fps={target}` для ВСЕХ входов и `setpts=PTS-STARTPTS` 
   для сброса таймстемпов, чтобы все потоки начинались ровно с 0.
3. Ограничение FPS: LED-экраны Kystar физически не могут плавно отображать 60 FPS,
   поэтому мы принудительно ограничиваем финальный FPS до 30 (`_MAX_OUTPUT_FPS`),
   чтобы не перегружать аппаратный декодер и сеть.
"""

import logging
import subprocess
from datetime import datetime
from pathlib import Path

from src.core import config
from src.core.media_utils import get_media_duration, get_media_fps, has_audio_stream

logger = logging.getLogger(__name__)

# Расширения, которые FFmpeg должен обрабатывать как видео-потоки
_VIDEO_LIKE_EXTENSIONS = config.VIDEO_EXTENSIONS | {".gif"}

# Максимальный FPS для выхода (ограничиваем, т.к. LED-экран не тянет 60fps)
_MAX_OUTPUT_FPS = 30
_DEFAULT_FPS = 25


class FFmpegRenderer:
    """Класс для сборки многозонных сцен через FFmpeg."""
    
    def __init__(self, output_dir: str = "rendered_scenes"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def _cleanup_old_scenes(self, max_files: int = 5):
        """
        Очищает старые сгенерированные файлы, оставляя только `max_files` самых новых,
        чтобы избежать переполнения диска ПК.
        """
        try:
            if not self.output_dir.exists():
                return
            
            # Получаем список всех файлов в папке, сортируем по времени изменения (от старых к новым)
            files = sorted(
                self.output_dir.iterdir(),
                key=lambda p: p.stat().st_mtime
            )
            
            # Оставляем только `max_files` самых новых
            files_to_delete = files[:-max_files] if len(files) > max_files else []
            
            for file_path in files_to_delete:
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        logger.debug("Очищен старый файл сцены: %s", file_path)
                    except Exception as e:
                        logger.warning("Не удалось удалить старый файл %s: %s", file_path, e)
                        
        except Exception as e:
            logger.error("Ошибка при очистке старых сцен: %s", e)
        
    def render_scene(self, zones: list[dict], rows: int, cols: int) -> str:
        """
        Собирает сцену из зон.
        
        Если есть видео/GIF, рендерит .mp4 с длительностью самого длинного видео.
        Если только картинки, рендерит один .png.
        
        Args:
            zones: Список зон, каждая с ключами: row, col, rowSpan, colSpan, media.
            rows: Количество строк в сетке.
            cols: Количество колонок в сетке.
            
        Returns:
            str: Путь к итоговому файлу (mp4/png). Возвращает пустую строку при ошибке.
        """
        
        # Очищаем старый мусор с диска ПК перед новым рендером
        self._cleanup_old_scenes()
        
        if not zones:
            return ""

        panel_w = config.PANEL_WIDTH
        panel_h = config.PANEL_HEIGHT
        
        safe_w = max(1, cols * panel_w)
        safe_h = max(1, rows * panel_h)
        
        # Определяем, есть ли видео/GIF среди медиа
        has_video = any(
            Path(z["media"]).suffix.lower() in _VIDEO_LIKE_EXTENSIONS 
            for z in zones
        )
        
        # Определяем максимальную длительность и FPS
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
            
            # Целевой FPS = максимальный из источников, но не более лимита
            if fps_values:
                target_fps = min(max(fps_values), _MAX_OUTPUT_FPS)
            
            # Минимальная длительность
            if max_duration <= 0:
                max_duration = 15.0
                
            logger.info(
                "Видео-сцена: длительность=%.1f сек, FPS=%.1f", 
                max_duration, target_fps
            )
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = ".mp4" if has_video else ".png"
        output_file = str(self.output_dir / f"scene_{timestamp}{ext}")
        
        from src.core.ffmpeg_manager import get_ffmpeg_path
        cmd = [get_ffmpeg_path(), "-y"]
        
        # Добавляем инпуты
        for z in zones:
            media = str(z["media"])
            media_ext = Path(media).suffix.lower()
            
            if media_ext in _VIDEO_LIKE_EXTENSIONS:
                if media_ext == ".gif":
                    # GIF: зацикливаем и декодируем все кадры
                    cmd.extend(["-ignore_loop", "0"])
                # Видео/GIF — обычный вход
            else:
                # Картинка в видео-сцене
                if has_video:
                    cmd.extend(["-loop", "1", "-framerate", str(int(target_fps))])
                    
            cmd.extend(["-i", media])
            
        # Формируем filter_complex
        filters = []
        
        # Базовый фон с правильным FPS
        if has_video:
            filters.append(
                f"color=c=black:s={safe_w}x{safe_h}"
                f":d={max_duration}:r={int(target_fps)}[bg]"
            )
        else:
            filters.append(f"color=c=black:s={safe_w}x{safe_h}[bg]")
        
        # Масштабирование и нормализация FPS инпутов
        for i, z in enumerate(zones):
            target_w = z["colSpan"] * panel_w
            target_h = z["rowSpan"] * panel_h
            media_ext = Path(z["media"]).suffix.lower()
            
            if has_video:
                # Нормализуем все потоки к единому FPS + масштабирование
                # setpts=PTS-STARTPTS сбрасывает временные метки, чтобы overlay был синхронизирован
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
            
        # Наложение (overlay)
        prev_bg = "bg"
        for i, z in enumerate(zones):
            x = z["col"] * panel_w
            y = z["row"] * panel_h
            out_name = f"out{i}" if i < len(zones) - 1 else "final_out"
            
            if has_video:
                # eof_action=pass: когда поток заканчивается, последний кадр остаётся
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
            # Сначала применяем очистку шума (в RGB пространстве),
            # затем конвертируем обратно в YUV PC Range
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
                "-crf", "18",           # Высокое качество
                "-pix_fmt", "yuv420p",
                "-r", str(int(target_fps)),  # Явный выходной FPS
                "-movflags", "+faststart",    # Быстрый старт для стриминга
                "-color_primaries", "bt709",  # Точная передача цвета
                "-color_trc", "bt709",
                "-colorspace", "bt709",
                "-color_range", "pc"
            ])
            
            if config.LIMIT_BITRATE:
                cmd.extend([
                    "-maxrate", "4M",
                    "-bufsize", "8M",
                    "-g", str(int(target_fps))  # GOP = FPS (опорный кадр каждую секунду)
                ])
        else:
            cmd.extend(["-map", "[final_out]"])
            cmd.extend(["-vframes", "1"])
            
        cmd.append(output_file)
        
        logger.info("Запуск FFmpeg: %s", " ".join(cmd))
        
        # Запуск процесса
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
        Оптимизирует одиночное видео под размеры и требования LED-панели.
        Применяет те же настройки, что и render_scene (если включены в конфиге).
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
        
        # Настраиваем видео-фильтр
        # Используем подложку из чисто черного цвета, чтобы прозрачные GIF 
        # не получали белый фон после отбрасывания альфа-канала.
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
            logger.info("Запуск FFmpeg для оптимизации видео: %s", input_path)
            subprocess.run(cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            logger.info("Видео успешно оптимизировано: %s", output_file)
            return output_file
        except subprocess.CalledProcessError as e:
            logger.error("Ошибка FFmpeg (оптимизация): %s", e)
            return ""
