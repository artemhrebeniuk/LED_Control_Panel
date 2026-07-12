# -*- coding: utf-8 -*-
"""
kystar_client.py — Чистый API-клиент для медиаплеера Kystar KD6.

Этот модуль содержит ТОЛЬКО сетевую логику:
- HTTP GET/POST запросы к устройству
- Расчёт MD5-хэшей файлов
- Двухэтапный протокол загрузки медиа
- Сборку JSON-пакетов для API

Никакого PyQt6 или UI-кода здесь нет. Все методы являются
блокирующими (синхронными) и должны вызываться исключительно
из рабочих потоков (QThread), чтобы не блокировать UI.
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
    """Базовое исключение для ошибок API-клиента Kystar."""


class KystarClient:
    """
    Синхронный HTTP-клиент для управления медиаплеером Kystar KD6.

    Все методы выполняют блокирующие HTTP-запросы через библиотеку requests.
    Для использования в PyQt6 вызывайте эти методы ТОЛЬКО из QThread-воркеров.

    Attributes:
        base_url: Базовый URL API (http://IP:18080).
        reboot_url: URL для перезагрузки (http://IP:18081).
        timeout: Таймаут HTTP-запросов в секундах.
        session: Переиспользуемая HTTP-сессия для keep-alive соединений.
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
        # Переиспользуем сессию для эффективности TCP-соединений
        self.session = requests.Session()

    def __del__(self) -> None:
        """Закрывает HTTP сессию при уничтожении объекта."""
        try:
            self.session.close()
        except Exception:
            pass

    def update_urls(self, base_url: str, reboot_url: str) -> None:
        """Обновляет URL-адреса для связи с устройством."""
        self.base_url = base_url
        self.reboot_url = reboot_url
        self.abort_all_requests()

    def abort_all_requests(self) -> None:
        """Принудительно закрывает все активные сетевые соединения.
        Полезно для прерывания долгой загрузки при закрытии приложения."""
        try:
            self.session.close()
            # Пересоздаем сессию для возможности последующих запросов
            self.session = requests.Session()
        except Exception as e:
            logger.debug("Ошибка при обрыве соединений: %s", e)

    # ================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ================================================================

    def _get(self, endpoint: str, url_base: str | None = None, **kwargs) -> dict[str, Any]:
        """
        Выполняет HTTP GET запрос к API устройства.

        Args:
            endpoint: Путь эндпоинта (например, '/device').
            url_base: Альтернативный базовый URL (для порта 18081).
            **kwargs: Дополнительные параметры для requests.get().

        Returns:
            Распарсенный JSON-ответ в виде словаря.

        Raises:
            KystarClientError: При ошибке соединения или невалидном ответе.
        """
        base = url_base or self.base_url
        url = f"{base}/{endpoint.lstrip('/')}"
        try:
            response = self.session.get(url, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            raise KystarClientError(f"Нет соединения с устройством: {e}") from e
        except requests.exceptions.Timeout as e:
            raise KystarClientError(f"Таймаут запроса к {url}: {e}") from e
        except requests.exceptions.RequestException as e:
            raise KystarClientError(f"Ошибка HTTP запроса: {e}") from e
        except json.JSONDecodeError as e:
            raise KystarClientError(f"Невалидный JSON в ответе: {e}") from e

    def _post(self, endpoint: str, params: dict | None = None,
              data: Any = None, files: dict | None = None,
              json_data: Any = None, **kwargs) -> dict[str, Any]:
        """
        Выполняет HTTP POST запрос к API устройства.

        Args:
            endpoint: Путь эндпоинта.
            params: Query-параметры URL (?key=value).
            data: Тело запроса (form-encoded).
            files: Файлы для multipart-загрузки.
            json_data: JSON-тело запроса.
            **kwargs: Дополнительные параметры для requests.post().

        Returns:
            Распарсенный JSON-ответ.

        Raises:
            KystarClientError: При ошибке соединения или невалидном ответе.
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
            raise KystarClientError(f"Нет соединения с устройством: {e}") from e
        except requests.exceptions.Timeout as e:
            raise KystarClientError(f"Таймаут запроса к {url}: {e}") from e
        except requests.exceptions.RequestException as e:
            raise KystarClientError(f"Ошибка HTTP запроса: {e}") from e
        except json.JSONDecodeError as e:
            raise KystarClientError(f"Невалидный JSON в ответе: {e}") from e

    # ================================================================
    # ИНФОРМАЦИЯ ОБ УСТРОЙСТВЕ
    # ================================================================

    def ping(self) -> bool:
        """
        Проверяет доступность устройства по сети.

        Выполняет GET /device с коротким таймаутом (2 сек).
        Используется фоновым PingWorker для обновления индикатора статуса.

        Returns:
            True если устройство доступно, False если нет.
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
        Получает детальную информацию об устройстве.

        Эндпоинт: GET /device

        Returns:
            Словарь с полями: appVersion, deviceName, screenWidth,
            screenHeight, usableSpace, totalSpace и др.
        """
        result = self._get("device")
        return result.get("data", result)

    def get_screen_params(self) -> dict[str, Any]:
        """
        Получает текущие параметры экрана (яркость, громкость, состояние).

        Эндпоинт: GET /getScreenParams

        Returns:
            Словарь с полями: bright (0-100), voice (0-1),
            screenOn (bool), contrast (int).
        """
        return self._get("getScreenParams")

    # ================================================================
    # УПРАВЛЕНИЕ ЭКРАНОМ
    # ================================================================

    def set_brightness(self, value: int) -> dict[str, Any]:
        """
        Устанавливает яркость экрана.

        Эндпоинт: POST /setting/bright?bright=N

        Args:
            value: Значение яркости от 0 (выключено) до 100 (максимум).

        Returns:
            Ответ API (code: 200 при успехе).
        """
        # Ограничиваем значение допустимым диапазоном
        value = max(0, min(100, value))
        logger.info("Установка яркости: %d", value)
        return self._post("setting/bright", params={"bright": value})

    def set_screen_power(self, on: bool) -> dict[str, Any]:
        """
        Включает или выключает экран.

        Эндпоинт: POST /setting/screen?screen=true|false

        Args:
            on: True для включения, False для выключения.

        Returns:
            Ответ API.
        """
        screen_value = "true" if on else "false"
        logger.info("Экран: %s", "ВКЛ" if on else "ВЫКЛ")
        return self._post("setting/screen", params={"screen": screen_value})

    def reboot(self) -> dict[str, Any]:
        """
        Перезагружает медиаплеер.

        Эндпоинт: GET :18081/reboot (ВНИМАНИЕ: порт 18081, не 18080!)

        Returns:
            Ответ API.
        """
        logger.warning("Отправлена команда перезагрузки устройства")
        return self._get("reboot", url_base=self.reboot_url)



    # ================================================================
    # МЕДИАФАЙЛЫ: ДВУХЭТАПНЫЙ ПРОТОКОЛ ЗАГРУЗКИ
    # ================================================================

    @staticmethod
    def calculate_md5_and_length(file_path: str) -> str:
        """
        Вычисляет строку md5AndLength для идентификации файла на устройстве.

        Алгоритм из документации Kystar:
        1. Читаем первые 1 МБ (1024 * 1024 байт) файла.
           Если файл меньше 1 МБ — читаем весь файл.
        2. Вычисляем MD5-хэш от прочитанного фрагмента.
        3. Формируем строку: "{md5_hex}-{полный_размер_файла_в_байтах}"

        Args:
            file_path: Абсолютный путь к файлу.

        Returns:
            Строка вида "dddae1f8cb4bdc55b88f6d03edfc6ac2-952324".

        Raises:
            FileNotFoundError: Если файл не найден.
        """
        file_size = os.path.getsize(file_path)

        # Читаем первый мегабайт для расчёта MD5
        chunk_size = 1024 * 1024  # 1 МБ
        md5_hash = hashlib.md5()

        with open(file_path, "rb") as f:
            chunk = f.read(chunk_size)
            md5_hash.update(chunk)

        md5_hex = md5_hash.hexdigest()
        md5_and_length = f"{md5_hex}-{file_size}"

        logger.debug("MD5: %s для файла %s", md5_and_length, file_path)
        return md5_and_length

    def check_upload(self, md5_and_length: str) -> bool:
        """
        Проверяет, загружен ли файл на устройство.

        Эндпоинт: POST /checkUpload?md5andlength=X

        Args:
            md5_and_length: Идентификатор файла (md5-size).

        Returns:
            True если файл уже существует на устройстве (code=200),
            False если файла нет (code=406).
        """
        try:
            result = self._post("checkUpload", params={"md5andlength": md5_and_length})
            exists = result.get("code") == 200
            logger.info(
                "Проверка файла %s: %s",
                md5_and_length,
                "найден" if exists else "не найден",
            )
            return exists
        except KystarClientError:
            return False

    def get_all_media(self) -> list[dict[str, Any]]:
        """
        Получает список всех медиафайлов, загруженных на устройство.

        Эндпоинт: GET /medias

        Returns:
            Список словарей с информацией о медиафайлах (md5AndLength, name, size, type).
        """
        try:
            result = self._get("medias")
            return result.get("data", [])
        except KystarClientError as e:
            logger.debug("Ошибка получения списка медиа: %s", e)
            return []

    def delete_media(self, md5_and_length: str) -> tuple[bool, str]:
        """
        Удаляет медиафайл с устройства для освобождения памяти.

        Эндпоинт: POST /deleteMedia?md5AndLength={md5_and_length}

        Args:
            md5_and_length: Идентификатор файла.

        Returns:
            (bool, str): Успешность операции и сообщение.
        """
        try:
            result = self._post("deleteMedia", params={"md5AndLength": md5_and_length})
            code = result.get("code")
            if code == 200:
                logger.info("Файл удален с устройства: %s", md5_and_length)
                return True, "Успех"
            elif code == 501:
                return False, "Файл сейчас воспроизводится"
            else:
                msg = result.get("message", "Неизвестная ошибка")
                return False, msg
        except KystarClientError as e:
            logger.debug("Ошибка при удалении файла %s: %s", md5_and_length, e)
            return False, str(e)

    def upload_media(
        self,
        file_path: str,
        progress_callback: Any = None,
    ) -> str:
        """
        Загружает медиафайл на устройство.

        Двухэтапный протокол:
        1. Вычисляет md5AndLength файла.
        2. Проверяет наличие через checkUpload.
        3. Если файла нет — загружает через POST /uploadMedia/{type}/{md5_and_length}.

        Эндпоинт: POST /uploadMedia/{mediaType}/{md5AndLength}

        Args:
            file_path: Путь к локальному медиафайлу.
            progress_callback: Опциональный callable(percent: int) для прогресса.

        Returns:
            Строка md5AndLength загруженного файла.

        Raises:
            KystarClientError: При ошибке загрузки.
            ValueError: Если тип файла не поддерживается.
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        # Определяем тип медиа (1=видео, 2=изображение)
        media_type = get_media_type(extension)
        if media_type is None:
            raise ValueError(f"Неподдерживаемый тип файла: {extension}")

        # Шаг 1: Вычисляем идентификатор файла
        if progress_callback:
            progress_callback(10)
        md5_and_length = self.calculate_md5_and_length(file_path)

        # Шаг 2: Проверяем, есть ли файл на устройстве
        if progress_callback:
            progress_callback(20)
        if self.check_upload(md5_and_length):
            logger.info("Файл уже на устройстве: %s", md5_and_length)
            if progress_callback:
                progress_callback(100)
            return md5_and_length

        # Шаг 3: Загружаем файл (multipart POST)
        if progress_callback:
            progress_callback(30)

        endpoint = f"uploadMedia/{media_type}/{md5_and_length}"
        url = f"{self.base_url}/{endpoint}"

        logger.info("Загрузка файла: %s → %s", path.name, url)

        # Открываем файл и отправляем как multipart/form-data
        # Увеличиваем таймаут для больших файлов
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
                    f"Ошибка загрузки: code={result.get('code')}, "
                    f"message={result.get('message')}"
                )

            logger.info("Файл успешно загружен: %s", md5_and_length)
            if progress_callback:
                progress_callback(100)
            return md5_and_length

        except requests.exceptions.RequestException as e:
            raise KystarClientError(f"Ошибка при загрузке файла: {e}") from e

    def stop_playback(self) -> bool:
        """
        Останавливает текущее воспроизведение.
        Использует вызов playText с пустым текстом, который по документации 
        автоматически отменяет текущую программу (что освобождает медиафайлы).
        """
        try:
            params = {
                "text": " ",
                "width": screen_config.total_width,
                "height": screen_config.total_height,
                "scrollSpeed": 1,
                "color": -1,
                "backgroundColor": 0, # 0 = прозрачный
                "fontSize": 10
            }
            logger.info("Остановка воспроизведения (через playText)")
            result = self._post("playText", params=params)
            return result.get("code") == 200
        except Exception as e:
            logger.warning(f"Не удалось остановить воспроизведение: {e}")
            return False

    def upload_third_program(
        self,
        media_items: list[dict[str, Any]],
        program_name: str = "PyQt6 Program",
    ) -> dict[str, Any]:
        """
        Создаёт и немедленно запускает программу с медиа-контентом.

        Эндпоинт: POST /uploadThirdProgram

        Формирует JSON-программу со списком медиафайлов и отправляет
        на устройство. После успешной загрузки контент сразу воспроизводится.

        Args:
            media_items: Список медиа. Каждый элемент — словарь с ключами:
                - md5AndLength (str): Идентификатор файла.
                - duration (int): Длительность показа в мс.
                - anim (str, optional): Спецэффект перехода.
            program_name: Имя программы для отображения на устройстве.

        Returns:
            Ответ API (code: 200 при успехе).
        """
        # Формируем JSON-программу по спецификации Kystar
        program_data = {
            "name": program_name,
            "width": screen_config.total_width,
            "height": screen_config.total_height,
            "mediaList": media_items,
        }

        logger.info(
            "Отправка программы '%s' с %d медиа-элементами",
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
        Оркестрирует полный процесс публикации медиа.

        Args:
            program_name: Имя программы для отображения на устройстве.
            file_paths: Список путей к локальным медиафайлам.
            image_duration_sec: Длительность показа каждого изображения (в секундах).
            progress_callback: Опциональный callable(percent: int).

        Returns:
            Ответ API от uploadThirdProgram.
        """
        media_list: list[dict[str, Any]] = []
        total_files = len(file_paths)

        for idx, file_path in enumerate(file_paths):
            path = Path(file_path)
            extension = path.suffix.lower()
            media_type = get_media_type(extension)

            if media_type is None:
                logger.warning("Пропуск файла с неизвестным типом: %s", file_path)
                continue

            # Прогресс: равномерно распределяем 0-80% на загрузку файлов
            base_progress = int((idx / total_files) * 80)

            def file_progress(p: int, _base: int = base_progress) -> None:
                if progress_callback:
                    # Преобразуем прогресс файла (0-100) в общий прогресс
                    overall = _base + int((p / 100) * (80 / total_files))
                    progress_callback(min(overall, 80))

            # Загружаем файл на устройство
            md5_and_length = self.upload_media(file_path, progress_callback=file_progress)

            # Определяем длительность показа
            if media_type == MEDIA_TYPE_IMAGE:
                duration = image_duration_sec * 1000
            else:
                # Для видео ставим 0 — плеер сам определит длительность
                duration = 0

            media_list.append({
                "md5AndLength": md5_and_length,
                "duration": duration,
                "anim": "NONE",
            })

        if not media_list:
            raise KystarClientError("Нет подходящих медиафайлов для воспроизведения")

        # Отправляем программу на воспроизведение
        if progress_callback:
            progress_callback(85)

        result = self.upload_third_program(media_list)

        if progress_callback:
            progress_callback(100)

        return result

    def set_input_source(self, source_type: int, width: int = 1920, height: int = 1080) -> bool:
        """
        Переключает источник видеосигнала (HDMI / Android).
        
        Args:
            source_type: 2 (Android/Внутренний плеер), 3 (HDMI/Внешний кабель).
            width: Ширина области (экрана)
            height: Высота области (экрана)
            
        Returns:
            bool: True при успехе, False при ошибке
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
                logger.info("Источник сигнала успешно переключен на: %s", source_type)
                return True
                
            logger.error("Ошибка при переключении источника: %s", data.get("message"))
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error("Сетевая ошибка при переключении источника: %s", e)
            return False

    # ================================================================
    # ОКНА (WINDOWS)
    # ================================================================

    def set_windows(self, windows: list[dict[str, int]]) -> dict[str, Any]:
        """
        Создаёт или модифицирует список окон на экране.


        Эндпоинт: POST /setWindows

        Args:
            windows: Список окон. Каждое окно — словарь:
                - index (int): Порядковый номер окна (начиная с 0).
                - x (int): Горизонтальная позиция в пикселях.
                - y (int): Вертикальная позиция в пикселях.
                - w (int): Ширина окна в пикселях.
                - h (int): Высота окна в пикселях.

        Returns:
            Ответ API.
        """
        return self._post("setWindows", json_data=windows)

    def set_fullscreen_window(self) -> dict[str, Any]:
        """
        Устанавливает одно полноэкранное окно на весь экран.

        Размеры окна автоматически берутся из screen_config.

        Returns:
            Ответ API.
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
        Получает информацию о картах отправки и приёма.

        Эндпоинт: GET /getCardInfo

        Используется для мониторинга: количество приёмных карт (rxNum)
        и их версии позволяют определить, все ли модули подключены.

        Returns:
            Словарь с полями: rxNum (int), rxCardList (list), txCard (dict).
        """
        result = self._get("getCardInfo")
        return result.get("data", result)

    def get_current_windows(self) -> dict[str, Any]:
        """
        Получает текущую конфигурацию окон.

        Эндпоинт: GET /curWindows

        Returns:
            Ответ API с массивом окон в поле data.
        """
        return self._get("curWindows")
