"""Иерархия валют: ABC Currency, фиатные и криптовалюты.

FiatCurrency и CryptoCurrency наследуются от ABC Currency и
обязаны реализовать метод formatting(). Создание объектов -
только через функцию get_currency().
"""

from abc import ABC, abstractmethod


class Currency(ABC):
    """Абстрактная базовая валюта.

    ABC используется как контракт: гарантирует,
    что у любой валюты есть code, name, symbol и formatting().
    """

    def __init__(self, code: str, name: str, symbol: str | None = None) -> None:
        """Инициализирует общие поля валюты."""
        self._code = code
        self._name = name
        self._symbol = symbol

    @property
    def code(self) -> str:
        """Код валюты (например, USD или BTC)."""
        return self._code

    @property
    def name(self) -> str:
        """Человеческое название валюты."""
        return self._name

    @property
    def symbol(self) -> str | None:
        """Символ валюты, если есть ($, ₽, ₿)."""
        return self._symbol

    @abstractmethod
    def formatting(self, amount: float) -> str:
        """Возвращает сумму в формате, специфичном для типа валюты."""


class FiatCurrency(Currency):
    """Фиатная валюта: сумма выводится с двумя знаками после запятой."""

    def formatting(self, amount: float) -> str:
        """Форматирует сумму: 2 знака + символ, если есть."""
        formatted = f"{amount:,.2f}".replace(",", " ")
        if self._symbol:
            return f"{formatted} {self._symbol}"
        return f"{formatted} {self._code}"


class CryptoCurrency(Currency):
    """Криптовалюта: сумма выводится с восемью знаками после запятой."""

    def formatting(self, amount: float) -> str:
        """Форматирует сумму: 8 знаков + символ, если есть."""
        formatted = f"{amount:.8f}".rstrip("0").rstrip(".")
        if self._symbol:
            return f"{formatted} {self._symbol}"
        return f"{formatted} {self._code}"


# Реестр валют

_FIAT_CODES: dict[str, tuple[str, str, str]] = {
    "USD": ("US Dollar", "United States", "$"),
    "EUR": ("Euro", "European Union", "€"),
    "GBP": ("British Pound Sterling", "United Kingdom", "£"),
    "RUB": ("Russian Ruble", "Russia", "₽"),
}

_CRYPTO_CODES: dict[str, tuple[str, str]] = {
    "BTC": ("Bitcoin", "₿"),
    "ETH": ("Ethereum", "Ξ"),
    "SOL": ("Solana", "◎"),
}

_registry: dict[str, Currency] = {}


def _build_registry() -> None:
    """Заполняет реестр объектов валют."""
    if _registry:
        return
    for code, (name, issuer, symbol) in _FIAT_CODES.items():
        _registry[code] = FiatCurrency(code, name, symbol)
    for code, (name, symbol) in _CRYPTO_CODES.items():
        _registry[code] = CryptoCurrency(code, name, symbol)


def get_currency(code: str) -> Currency:
    """Возвращает объект валюты по коду.
    CurrencyNotFoundError, если валюта неизвестна.
    """
    _build_registry()
    from valutatrade_hub.core.exceptions import CurrencyNotFoundError

    normalized = code.strip().upper()
    currency = _registry.get(normalized)
    if currency is None:
        raise CurrencyNotFoundError(code)
    return currency


def list_known_currencies() -> set[str]:
    """Множество всех известных кодов валют."""
    _build_registry()
    return set(_registry)
