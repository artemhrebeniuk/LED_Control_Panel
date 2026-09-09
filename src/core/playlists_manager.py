from __future__ import annotations
"""
playlists_manager.py — Local playlist persistence manager storing configuration in JSON.
"""
import json
import os
from pathlib import Path
from typing import Any

PLAYLISTS_FILE = "data/playlists.json"


class PlaylistsManager:
    """Manages creation, loading, editing, and persistence of playlists (programs)."""

    def __init__(self, filepath: str = PLAYLISTS_FILE) -> None:
        self.filepath = Path(filepath)
        self.programs: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Loads playlists from JSON file or generates default initial program."""
        if not self.filepath.exists():
            self.programs = [
                {"id": "default", "name": "Program 1", "files": []}
            ]
            self._save()
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.programs = json.load(f)
        except Exception:
            self.programs = [
                {"id": "default", "name": "Program 1", "files": []}
            ]

    def _save(self) -> None:
        """Serializes active playlists to JSON storage."""
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.programs, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving playlists: {e}")

    def get_all_programs(self) -> list[dict[str, Any]]:
        """Returns all configured programs."""
        return self.programs

    def add_program(self, name: str) -> dict[str, Any]:
        """Creates and appends a new playlist program."""
        import uuid
        prog_id = str(uuid.uuid4())
        prog = {"id": prog_id, "name": name, "files": []}
        self.programs.append(prog)
        self._save()
        return prog

    def rename_program(self, prog_id: str, new_name: str) -> None:
        """Renames an existing program by ID."""
        for p in self.programs:
            if p["id"] == prog_id:
                p["name"] = new_name
                self._save()
                break

    def delete_program(self, prog_id: str) -> None:
        """Deletes a program by ID. The last remaining program cannot be deleted."""
        if len(self.programs) <= 1:
            return
        self.programs = [p for p in self.programs if p["id"] != prog_id]
        self._save()

    def get_program_files(self, prog_id: str) -> list[str]:
        """Returns the list of media file paths associated with a program."""
        for p in self.programs:
            if p["id"] == prog_id:
                return p.get("files", [])
        return []

    def set_program_files(self, prog_id: str, file_paths: list[str]) -> None:
        """Updates the media file list for a specific program."""
        for p in self.programs:
            if p["id"] == prog_id:
                p["files"] = file_paths
                self._save()
                break
