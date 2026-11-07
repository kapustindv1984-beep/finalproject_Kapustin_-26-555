"""Хранилище Parser Service: кеш курсов и журнал измерений.

rates.json - снимок последних курсов,  читает Core Service.
exchange_rates.json - история всех измерений для последующего анализа.
Запись: сначала во временный файл, затем rename.
"""
import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path

from valutatrade_hub.parser_service.config import parser_config

logger = logging.getLogger(__name__)

def _atomic_write(path: Path, data: dict | list) -> None:
    """Атомарно записывает data в path: tmp-файл, затем os.replace."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def read_cache() -> dict:
    """Читает кеш rates.json; если файла нет, возвращает пустую структуру."""
    path = Path(parser_config.RATES_FILE_PATH)
    if not path.exists():
        return {"pairs": {}, "last_refresh": None}
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def write_cache(rates: dict[str, float], sources: dict[str, str]) -> None:
    """Сохраняет объединённый срез курсов в rates.json."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = {
        "pairs": {
            pair: {
                "rate": rate,
                "updated_at": now_iso,
                "source": sources[pair],
            }
            for pair, rate in rates.items()
        },
        "source": "ParserService",
        "last_refresh": now_iso,
    }
    _atomic_write(Path(parser_config.RATES_FILE_PATH), data)


def read_history() -> list[dict]:
    """Читает историю измерений; если файла нет, возвращает пустой список."""
    path = Path(parser_config.HISTORY_FILE_PATH)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    if isinstance(data, list):
        return data
    # Файл в неожиданном формате (например, словарь от старой версии) —
    # считаем историю пустой и не падаем при первом обновлении
    logger.warning("exchange_rates.json has unexpected format, starting fresh")
    return []


def append_history(rates: dict[str, float], source: str, request_ms: int) -> None:
    """Дописывает измерения одного клиента в exchange_rates.json.
    id каждой записи строится как <FROM>_<TO>_<ISO-UTC>.
    """
    history = read_history()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for pair, rate in rates.items():
        from_code, to_code = pair.split("_", 1)
        history.append({
            "id": f"{pair}_{now_iso}",
            "from_currency": from_code,
            "to_currency": to_code,
            "rate": rate,
            "timestamp": now_iso,
            "source": source,
            "meta": {
                "raw_id": None,
                "request_ms": request_ms,
                "status_code": 200,
                "etag": None,
            },
        })
    _atomic_write(Path(parser_config.HISTORY_FILE_PATH), history)
