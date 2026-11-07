"""Конфигурация Parser Service: ключи API, эндпоинты, списки валют, пути.

API-ключ хранится в переменной окружения EXCHANGERATE_API_KEY
(файл .env в корне проекта, не отслеживается git-ом) — по требованию
безопасности ключ не держим в коде.
"""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from valutatrade_hub.infra.settings import PROJECT_ROOT

# Загружаем переменные из .env один раз при импорте модуля
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class ParserConfig:
    """Все изменяемые параметры Parser Service в одном месте."""

    # Ключ загружается из переменной окружения
    EXCHANGERATE_API_KEY: str = field(default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY", ""))

    # Эндпоинты
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Списки валют
    BASE_FIAT_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict = field(default_factory=lambda: {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
    })

    # Пути к файлам хранилища
    RATES_FILE_PATH: str = str(PROJECT_ROOT / "data" / "rates.json")
    HISTORY_FILE_PATH: str = str(PROJECT_ROOT / "data" / "exchange_rates.json")

    # Сетевые параметры
    REQUEST_TIMEOUT: int = 10


parser_config = ParserConfig()
