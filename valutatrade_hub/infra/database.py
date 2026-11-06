"""Singleton DatabaseManager: безопасная абстракция над JSON-хранилищем."""

import json
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Self

from valutatrade_hub.infra.settings import PROJECT_ROOT, SettingsLoader


class DatabaseManager:
    """Единственный экземпляр доступа к JSON-файлам проекта.

    Отвечает за чтение, запись и безопасные транзакции
    «чтение → модификация → запись» над файлами в data/.

    Реализован через __new__: как и SettingsLoader, для единообразия.
    """

    _instance: DatabaseManager | None = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> Self:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._settings = SettingsLoader()
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _path(self, key: str) -> Path:
        """Возвращает абсолютный путь к файлу хранилища по ключу настроек."""
        return PROJECT_ROOT / self._settings.get(key)


    def _file_lock(self, path: Path) -> threading.Lock:
        """Отдельный lock на каждый файл - разные файлы не блокируют друг друга."""
        with self._locks_guard:
            if path not in self._locks:
                self._locks[path] = threading.Lock()
            return self._locks[path]

    def read(self, key: str, default: Any = None) -> Any:
        """Читает JSON-файл; при отсутствии файла возвращает default."""
        path = self._path(key)
        with self._file_lock(path):
            if not path.exists():
                return default
            return json.loads(path.read_text(encoding="utf-8"))

    def write(self, key: str, data: Any) -> None:
        """Атомарно записывает данные: tmp-файл → rename."""
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with self._file_lock(path):
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, path)

    def transaction(self, key: str, mutator: Callable[[Any], Any], default: Any = None) -> Any:
        """Безопасная операция: читает файл, применяет mutator, атомарно пишет.

        mutator получает текущее содержимое (или default) и возвращает
        новое состояние, которое сохраняется на диск.
        """
        path = self._path(key)
        with self._file_lock(path):
            current = default
            if path.exists():
                current = json.loads(path.read_text(encoding="utf-8"))
            new_data = mutator(current)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(new_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, path)
            return new_data
