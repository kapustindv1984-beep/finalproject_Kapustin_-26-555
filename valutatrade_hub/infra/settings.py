"""Singleton SettingsLoader: единая точка конфигурации проекта."""

import json
import threading
from pathlib import Path
from typing import Any, Self

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG: dict[str, Any] = {
    "users_file": "data/users.json",
    "portfolios_file": "data/portfolios.json",
    "rates_file": "data/rates.json",
    "history_file": "data/exchange_rates.json",
    "rates_ttl_seconds": 300,
    "default_base_currency": "USD",
    "log_dir": "logs",
    "log_file": "logs/actions.log",
    "log_level": "INFO",
    "log_format": "text",
}


class SettingsLoader:
    """Единственный экземпляр настроек приложения (Singleton).

    Способ реализации — через __new__: проще и читабельнее метакласса,
    а double-checked locking гарантирует один экземпляр даже при
    конкурентных вызовах из разных потоков.
    """

    _instance: SettingsLoader | None = None
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
        self._lock = threading.Lock()
        self._config: dict[str, Any] = dict(DEFAULT_CONFIG)
        self.reload()

    def reload(self) -> None:
        """Перечитывает config.json (если есть) поверх значений по умолчанию."""
        with self._lock:
            path = PROJECT_ROOT / "config.json"
            if path.exists():
                loaded = json.loads(path.read_text(encoding="utf-8"))
                self._config = {**DEFAULT_CONFIG, **loaded}

    def get(self, key: str, default: Any = None) -> Any:
        """Возвращает значение настройки или default, если ключа нет."""
        with self._lock:
            return self._config.get(key, default)
