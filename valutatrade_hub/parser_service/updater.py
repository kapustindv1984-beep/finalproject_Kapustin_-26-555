"""RatesUpdater: координирует опрос API-клиентов и сохранение курсов.

Если один из клиентов падает - ошибка логируется, обновление
продолжается с данными остальных.
"""
import logging
import time

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service import storage
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)

logger = logging.getLogger(__name__)


class RatesUpdater:
    """Точка входа Parser Service: опрашивает клиентов и обновляет кеш."""

    def __init__(self, clients: list[BaseApiClient] | None = None):
        self._clients = clients if clients is not None else [
            CoinGeckoClient(),
            ExchangeRateApiClient(),
        ]

    def run_update(self, source: str | None = None) -> dict:
        """Опрашивает клиентов, объединяет курсы и сохраняет их.

        source - необязательный фильтр по имени источника
        ('coingecko' или 'exchangerate'). Возвращает сводку обновления.
        """
        logger.info("Starting rates update...")
        merged_rates: dict[str, float] = {}
        merged_sources: dict[str, str] = {}
        errors: list[str] = []

        for client in self._clients:
            if source and client.source.lower() != source.lower():
                continue
            logger.info("Fetching from %s...", client.source)
            start = time.perf_counter()
            try:
                rates = client.fetch_rates()
            except ApiRequestError as exc:
                logger.error("Failed to fetch from %s: %s", client.source, exc)
                errors.append(f"{client.source}: {exc}")
                continue
            request_ms = round((time.perf_counter() - start) * 1000)

            logger.info("Fetching from %s... OK (%d rates)", client.source, len(rates))
            merged_rates.update(rates)
            merged_sources.update({pair: client.source for pair in rates})
            storage.append_history(rates, client.source, request_ms)

        if not merged_rates:
            logger.error("No rates fetched: all sources failed")
            return {"updated": 0, "last_refresh": None, "errors": errors}

        storage.write_cache(merged_rates, merged_sources)
        cache = storage.read_cache()
        last_refresh = cache["last_refresh"]
        logger.info("Writing %d rates to cache... Done", len(merged_rates))
        return {
            "updated": len(merged_rates),
            "last_refresh": last_refresh,
            "errors": errors,
        }
