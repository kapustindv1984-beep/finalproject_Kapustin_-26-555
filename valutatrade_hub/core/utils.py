"""Вспомогательные функции: валидация валютных кодов и сумм."""

import re

CURRENCY_CODE_PATTERN = re.compile(r"^[A-Z]{2,5}$")


def validate_currency_code(code: str) -> str:
    """Проверяет код валюты: непустой, верхний регистр, 2-5 символов."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    normalized = code.strip().upper()
    if not CURRENCY_CODE_PATTERN.match(normalized):
        raise ValueError(
            f"Некорректный код валюты '{code}': ожидается 2-5 символов A-Z"
        )
    return normalized


def validate_amount(amount: object) -> float:
    """Проверяет, что сумма - положительное число (bool отсекается)."""
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise TypeError("'amount' должен быть положительным числом")
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return float(amount)
