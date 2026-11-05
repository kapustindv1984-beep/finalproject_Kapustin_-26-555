"""Бизнес-логика: register, login, show-portfolio, buy, sell, get-rate.
CLI не дублирует логику - только вызывает функции этого модуля.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.core.utils import validate_amount, validate_currency_code

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
USERS_FILE = DATA_DIR / "users.json"
PORTFOLIOS_FILE = DATA_DIR / "portfolios.json"
RATES_FILE = DATA_DIR / "rates.json"

RATES_TTL_SECONDS = 300  # переедет в SettingsLoader

# Стартовый капитал нового пользователя
STARTING_BALANCE_USD = 1000.0

# Заглушка. Заменить на Parser Service.
STUB_RATES: dict[str, float] = {
    "EUR_USD": 1.0786,
    "GBP_USD": 1.2665,
    "RUB_USD": 0.01016,
    "BTC_USD": 59337.21,
    "ETH_USD": 3720.00,
    "SOL_USD": 145.12,
}

# Текущая сессия (состояние консольного приложения)
_current_username: str | None = None


def _load_json(path: Path, default: Any) -> Any:
    """Читает JSON-файл; при отсутствии или ошибке возвращает default."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _save_json(path: Path, data: Any) -> None:
    """Атомарно записывает JSON: временный файл, затем rename."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _known_currencies() -> set[str]:
    """Множество всех известных кодов валют (USD + стороны пар)."""
    codes: set[str] = {"USD"}
    for pair in STUB_RATES:
        codes.update(pair.split("_"))
    return codes


def _find_user(username: str) -> User | None:
    """Ищет пользователя по имени в users.json."""
    for data in _load_json(USERS_FILE, []):
        if data["username"] == username:
            return User.from_dict(data)
    return None


def _get_portfolio(user_id: int) -> Portfolio:
    """Загружает портфель пользователя или создаёт пустой."""
    for data in _load_json(PORTFOLIOS_FILE, []):
        if data["user_id"] == user_id:
            return Portfolio.from_dict(data)
    return Portfolio(user_id=user_id)


def _save_portfolio(portfolio: Portfolio) -> None:
    """Сохраняет портфель, заменяя запись того же user_id."""
    portfolios = [
        p for p in _load_json(PORTFOLIOS_FILE, [])
        if p["user_id"] != portfolio.user_id
    ]
    portfolios.append(portfolio.to_dict())
    _save_json(PORTFOLIOS_FILE, portfolios)


def require_login() -> User:
    """Возвращает текущего пользователя или бросает PermissionError."""
    if _current_username is None:
        raise PermissionError("Сначала выполните login")
    user = _find_user(_current_username)
    if user is None:
        raise PermissionError("Сначала выполните login")
    return user


def register_user(username: str, password: str) -> str:
    """Создаёт пользователя и пустой портфель со стартовым капиталом."""
    if not username.strip():
        raise ValueError("Имя не может быть пустым")
    if len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")
    users = _load_json(USERS_FILE, [])
    if any(u["username"] == username for u in users):
        raise ValueError(f"Имя пользователя '{username}' уже занято")
    new_id = max((u["user_id"] for u in users), default=0) + 1
    user = User.create(new_id, username, password)
    users.append(user.to_dict())
    _save_json(USERS_FILE, users)
    portfolio = Portfolio(
        user_id=new_id,
        wallets={"USD": Wallet("USD", STARTING_BALANCE_USD)},
    )
    _save_portfolio(portfolio)
    return (
        f"Пользователь '{username}' зарегистрирован (id={new_id}). "
        f"Войдите: login --username {username} --password ****\n"
        f"Стартовый капитал: {STARTING_BALANCE_USD:,.2f} USD"
    )


def login_user(username: str, password: str) -> str:
    """Проверяет учётные данные и открывает сессию."""
    user = _find_user(username)
    if user is None:
        raise ValueError(f"Пользователь '{username}' не найден")
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")
    global _current_username
    _current_username = username
    return f"Вы вошли как '{username}'"


def show_portfolio(base: str = "USD") -> str:
    """Возвращает текстовое представление портфеля с итогом в base."""
    user = require_login()
    base = validate_currency_code(base)
    if base not in _known_currencies():
        raise CurrencyNotFoundError(base)
    portfolio = _get_portfolio(user.user_id)
    if not portfolio.wallets:
        return f"Портфель пользователя '{user.username}' пуст"
    pairs = _load_json(RATES_FILE, {"pairs": {}}).get("pairs", {})
    lines = [f"Портфель пользователя '{user.username}' (база: {base}):"]
    total = 0.0
    for code, wallet in sorted(portfolio.wallets.items()):
        if code == base:
            value = wallet.balance
        else:
            entry = pairs.get(f"{code}_{base}")
            if entry is None:
                lines.append(
                    f"- {code}: {wallet.balance:.4f} "
                    f"→ курс {code}→{base} недоступен"
                )
                continue
            value = wallet.balance * entry["rate"]
        total += value
        lines.append(f"- {code}: {wallet.balance:.4f} → {value:,.2f} {base}")
    lines.append("-" * 33)
    lines.append(f"ИТОГО: {total:,.2f} {base}")
    return "\n".join(lines)


def get_rate(from_code: str, to_code: str) -> tuple[float, str]:
    """Возвращает (курс, время обновления), при необходимости из заглушки."""
    from_code = validate_currency_code(from_code)
    to_code = validate_currency_code(to_code)
    known = _known_currencies()
    if from_code not in known:
        raise CurrencyNotFoundError(from_code)
    if to_code not in known:
        raise CurrencyNotFoundError(to_code)
    if from_code == to_code:
        return 1.0, datetime.now().isoformat(timespec="seconds")

    pair = f"{from_code}_{to_code}"
    entry = _load_json(RATES_FILE, {"pairs": {}}).get("pairs", {}).get(pair)
    if entry is not None:
        updated = datetime.fromisoformat(entry["updated_at"])
        age = (datetime.now() - updated).total_seconds()
        if age <= RATES_TTL_SECONDS:
            return float(entry["rate"]), entry["updated_at"]

    # Кеш отсутствует или устарел - обновляем из заглушки
    reverse = f"{to_code}_{from_code}"
    if pair in STUB_RATES:
        rate = STUB_RATES[pair]
    elif reverse in STUB_RATES:
        rate = 1.0 / STUB_RATES[reverse]
    else:
        raise ApiRequestError(
            f"Курс {from_code}→{to_code} недоступен. Повторите попытку позже."
        )
    updated_at = datetime.now().isoformat(timespec="seconds")
    data = _load_json(RATES_FILE, {"pairs": {}, "last_refresh": None})
    data.setdefault("pairs", {})[pair] = {
        "rate": rate,
        "updated_at": updated_at,
        "source": "Stub",
    }
    data["last_refresh"] = updated_at
    _save_json(RATES_FILE, data)
    return rate, updated_at


def get_rate_message(from_code: str, to_code: str) -> str:
    """Формирует сообщение для команды get-rate с обратным курсом."""
    rate, updated_at = get_rate(from_code, to_code)
    lines = [
        (
            f"Курс {from_code}→{to_code}: {rate:.8f} "
            f"(обновлено: {updated_at.replace('T', ' ')})"
        ),
    ]
    if from_code != to_code:
        lines.append(f"Обратный курс {to_code}→{from_code}: {1 / rate:,.4f}")
    return "\n".join(lines)


def buy_currency(currency: str, amount: float) -> str:
    """Покупает валюту за USD по текущему курсу."""
    user = require_login()
    currency = validate_currency_code(currency)
    amount = validate_amount(amount)
    if currency not in _known_currencies():
        raise CurrencyNotFoundError(currency)

    portfolio = _get_portfolio(user.user_id)
    if currency == "USD":
        wallet = portfolio.get_wallet("USD")
        if wallet is None:
            wallet = portfolio.add_currency("USD")
        was = wallet.balance
        wallet.deposit(amount)
        _save_portfolio(portfolio)
        return (
            f"Покупка выполнена: {amount:.4f} USD\n"
            f"Изменения в портфеле:\n"
            f"- USD: было {was:.4f} → стало {wallet.balance:.4f}"
        )

    rate, _ = get_rate(currency, "USD")
    cost = amount * rate
    usd_wallet = portfolio.get_wallet("USD")
    if usd_wallet is None:
        usd_wallet = portfolio.add_currency("USD")
    if usd_wallet.balance < cost:
        raise InsufficientFundsError(usd_wallet.balance, cost, "USD")
    usd_wallet.withdraw(cost)

    wallet = portfolio.get_wallet(currency)
    was = wallet.balance if wallet is not None else 0.0
    if wallet is None:
        wallet = portfolio.add_currency(currency)
    wallet.deposit(amount)
    _save_portfolio(portfolio)
    return (
        f"Покупка выполнена: {amount:.4f} {currency} "
        f"по курсу {rate:,.2f} USD/{currency}\n"
        f"Изменения в портфеле:\n"
        f"- {currency}: было {was:.4f} → стало {wallet.balance:.4f}\n"
        f"Оценочная стоимость покупки: {cost:,.2f} USD"
    )


def sell_currency(currency: str, amount: float) -> str:
    """Продаёт валюту за USD по текущему курсу."""
    user = require_login()
    currency = validate_currency_code(currency)
    amount = validate_amount(amount)
    if currency not in _known_currencies():
        raise CurrencyNotFoundError(currency)

    portfolio = _get_portfolio(user.user_id)
    wallet = portfolio.get_wallet(currency)
    if wallet is None:
        raise ValueError(
            f"У вас нет кошелька '{currency}'. Добавьте валюту: "
            f"она создаётся автоматически при первой покупке."
        )
    if wallet.balance < amount:
        raise InsufficientFundsError(wallet.balance, amount, currency)

    was = wallet.balance
    wallet.withdraw(amount)
    revenue = amount if currency == "USD" else amount * get_rate(currency, "USD")[0]
    if currency != "USD":
        usd_wallet = portfolio.get_wallet("USD")
        if usd_wallet is None:
            usd_wallet = portfolio.add_currency("USD")
        usd_wallet.deposit(revenue)
    _save_portfolio(portfolio)
    return (
        f"Продажа выполнена: {amount:.4f} {currency}\n"
        f"Изменения в портфеле:\n"
        f"- {currency}: было {was:.4f} → стало {wallet.balance:.4f}\n"
        f"Оценочная выручка: {revenue:,.2f} USD"
    )
