import json
import os
from pathlib import Path
from typing import Any

PLAYLISTS_FILE = "data/playlists.json"

class PlaylistsManager:
    """Управляет сохранением и загрузкой плейлистов (программ)."""

    def __init__(self, filepath: str = PLAYLISTS_FILE) -> None:
        self.filepath = Path(filepath)
        self.programs: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Загружает плейлисты из JSON файла."""
        if not self.filepath.exists():
            # Создаем дефолтную программу
            self.programs = [
                {"id": "default", "name": "Программа 1", "files": []}
            ]
            self._save()
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.programs = json.load(f)
        except Exception:
            self.programs = [
                {"id": "default", "name": "Программа 1", "files": []}
            ]

    def _save(self) -> None:
        """Сохраняет плейлисты в JSON файл."""
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.programs, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения плейлистов: {e}")

    def get_all_programs(self) -> list[dict[str, Any]]:
        return self.programs

    def add_program(self, name: str) -> dict[str, Any]:
        """Добавляет новую программу."""
        import uuid
        prog_id = str(uuid.uuid4())
        prog = {"id": prog_id, "name": name, "files": []}
        self.programs.append(prog)
        self._save()
        return prog

    def rename_program(self, prog_id: str, new_name: str) -> None:
        for p in self.programs:
            if p["id"] == prog_id:
                p["name"] = new_name
                self._save()
                break

    def delete_program(self, prog_id: str) -> None:
        """Удаляет программу по ID. Нельзя удалить последнюю программу."""
        if len(self.programs) <= 1:
            return
        self.programs = [p for p in self.programs if p["id"] != prog_id]
        self._save()

    def get_program_files(self, prog_id: str) -> list[str]:
        for p in self.programs:
            if p["id"] == prog_id:
                return p.get("files", [])
        return []

    def set_program_files(self, prog_id: str, file_paths: list[str]) -> None:
        """Обновляет список файлов для конкретной программы."""
        for p in self.programs:
            if p["id"] == prog_id:
                p["files"] = file_paths
                self._save()
                break
