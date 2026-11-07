"""API-клиенты Parser Service: CoinGecko (крипто) и ExchangeRate-API (фиат).

Каждый клиент изолирует детали внешнего API и приводит ответ
к единому формату: {"BTC_USD": 59337.21, ...}.
Ошибки сети и API оборачиваются в ApiRequestError.
"""

from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import parser_config

SOURCE_COINGECKO = "CoinGecko"
SOURCE_EXCHANGERATE = "ExchangeRate-API"


class BaseApiClient(ABC):
    """Единый интерфейс всех API-клиентов Parser Service."""

    source: str = ""

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Возвращает курсы в едином формате {PAIR_CODE: rate}."""


def _request_json(url: str, params: dict | None = None) -> dict:
    """Выполняет GET-запрос и возвращает разобранный JSON.
    Проверяет статус ответа и оборачивает сетевые ошибки
    в ApiRequestError.
    """
    try:
        response = requests.get(
            url,
            params=params,
            timeout=parser_config.REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout as exc:
        raise ApiRequestError(
            f"таймаут ответа ({parser_config.REQUEST_TIMEOUT} c)",
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise ApiRequestError(f"сетевая ошибка: {exc}") from exc

    if response.status_code == 429:
        raise ApiRequestError("превышен лимит запросов (429), подождите")
    if response.status_code in (401, 403):
        raise ApiRequestError("неверный или неактивный API-ключ")
    if response.status_code != 200:
        raise ApiRequestError(f"сервер вернул статус {response.status_code}")

    try:
        return response.json()
    except ValueError as exc:
        raise ApiRequestError("ответ не является корректным JSON") from exc


class CoinGeckoClient(BaseApiClient):
    """Клиент CoinGecko: курсы криптовалют к USD."""

    source = SOURCE_COINGECKO

    def fetch_rates(self) -> dict[str, float]:
        """Запрашивает курсы криптовалют и приводит их к формату пар."""
        vs = parser_config.BASE_FIAT_CURRENCY.lower()
        ids = ",".join(
            parser_config.CRYPTO_ID_MAP[code]
            for code in parser_config.CRYPTO_CURRENCIES
        )
        data = _request_json(
            parser_config.COINGECKO_URL, {"ids": ids, "vs_currencies": vs}
        )

        rates: dict[str, float] = {}
        for code in parser_config.CRYPTO_CURRENCIES:
            coin_id = parser_config.CRYPTO_ID_MAP[code]
            price = data.get(coin_id, {}).get(vs)
            if isinstance(price, (int, float)):
                rates[f"{code}_{parser_config.BASE_FIAT_CURRENCY}"] = float(price)
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Клиент ExchangeRate-API: курсы фиатных валют к USD."""

    source = SOURCE_EXCHANGERATE

    def fetch_rates(self) -> dict[str, float]:
        """Запрашивает курсы фиата и приводит их к формату пар."""
        base = parser_config.BASE_FIAT_CURRENCY
        url = f"{parser_config.EXCHANGERATE_API_URL}/{parser_config.EXCHANGERATE_API_KEY}/latest/{base}"
        data = _request_json(url)

        if data.get("result") != "success":
            error_type = data.get("error-type", "неизвестная ошибка API")
            raise ApiRequestError(f"ExchangeRate-API вернул ошибку: {error_type}")

        api_rates = data.get("rates") or data.get("conversion_rates") or {}
        rates: dict[str, float] = {f"{base}_{base}": 1.0}
        for code in parser_config.FIAT_CURRENCIES:
            value = api_rates.get(code)
            if isinstance(value, (int, float)) and value != 0:
                # API даёт курс "1 USD = value EUR", а кеш хранит EUR_USD,
                # поэтому переводим в обратную величину
                rates[f"{code}_{base}"] = round(1.0 / value, 6)
        return rates
