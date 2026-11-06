"""Настройка логирования: формат, уровень, ротация файлов."""

import logging
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import PROJECT_ROOT, SettingsLoader

_FORMAT = "%(levelname)s %(asctime)s %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S"


def setup_logging() -> logging.Logger:
    """Создаёт и возвращает настроенный логгер проекта.
    Уровень, путь и формат берутся из SettingsLoader. 
    """
    
    settings = SettingsLoader()
    logger = logging.getLogger("valutatrade_hub")

    if logger.handlers:  # защита от повторной настройки
        return logger

    logger.setLevel(settings.get("log_level", "INFO"))

    log_path = PROJECT_ROOT / settings.get("log_file", "logs/actions.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=100_000,  # ротация ~ каждые 100 КБ
        backupCount=5,     # хранится до 5 старых файлов (actions.log.1 и т.д.)
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    logger.addHandler(handler)
    logger.propagate = False

    return logger
