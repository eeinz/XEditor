"""Persistent application settings backed by QSettings."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings

from . import APP_ID, ORG_NAME


class Settings:
    def __init__(self) -> None:
        self._s = QSettings(ORG_NAME, APP_ID)

    # -- primitive helpers -------------------------------------------------
    def value(self, key: str, default=None):
        return self._s.value(key, default)

    def set_value(self, key: str, value) -> None:
        self._s.setValue(key, value)

    def bool(self, key: str, default: bool = False) -> bool:
        value = self._s.value(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def int(self, key: str, default: int = 0) -> int:
        try:
            return int(self._s.value(key, default))
        except (TypeError, ValueError):
            return default

    def text(self, key: str, default: str = "") -> str:
        value = self._s.value(key, default)
        return default if value is None else str(value)

    def byte_array(self, key: str) -> QByteArray | None:
        value = self._s.value(key)
        if isinstance(value, QByteArray):
            return value
        if isinstance(value, bytes):
            return QByteArray(value)
        return None

    def string_list(self, key: str) -> list[str]:
        value = self._s.value(key, [])
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        return [str(item) for item in value if str(item)]

    def sync(self) -> None:
        self._s.sync()

    # -- convenience --------------------------------------------------------
    def recent_files(self) -> list[str]:
        return self.string_list("files/recent")

    def set_recent_files(self, files: list[str]) -> None:
        self.set_value("files/recent", files[:12])

    def add_recent_file(self, path: str) -> list[str]:
        files = [item for item in self.recent_files() if item.lower() != path.lower()]
        files.insert(0, path)
        files = files[:12]
        self.set_recent_files(files)
        return files

    def remove_recent_file(self, path: str) -> list[str]:
        files = [item for item in self.recent_files() if item.lower() != path.lower()]
        self.set_recent_files(files)
        return files
