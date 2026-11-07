"""Бизнес-логика: register, login, show-portfolio, buy, sell, get-rate.
CLI не дублирует логику - только вызывает функции этого модуля.
"""

from datetime import datetime
from typing import Any

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    InsufficientFundsError,
)
from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.core.utils import validate_amount, validate_currency_code
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

# Синглтоны проекта: единая точка конфигурации и доступа к хранилищу
_settings = SettingsLoader()
_db = DatabaseManager()

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


def _find_user(username: str) -> User | None:
    """Ищет пользователя по имени в users.json."""
    for data in _db.read("users_file", default=[]):
        if data["username"] == username:
            return User.from_dict(data)
    return None


def _get_portfolio(user_id: int) -> Portfolio:
    """Загружает портфель пользователя или создаёт пустой."""
    for data in _db.read("portfolios_file", default=[]):
        if data["user_id"] == user_id:
            return Portfolio.from_dict(data)
    return Portfolio(user_id=user_id)


def _save_portfolio(portfolio: Portfolio) -> None:
    """Сохраняет портфель, заменяя запись того же user_id."""

    def _replace(portfolios: Any) -> list[dict[str, Any]]:
        portfolios = portfolios or []
        return [p for p in portfolios if p["user_id"] != portfolio.user_id] + [
            portfolio.to_dict()
        ]

    _db.transaction("portfolios_file", _replace, default=[])


def require_login() -> User:
    """Возвращает текущего пользователя или бросает PermissionError."""
    if _current_username is None:
        raise PermissionError("Сначала выполните login")
    user = _find_user(_current_username)
    if user is None:
        raise PermissionError("Сначала выполните login")
    return user


@log_action("REGISTER")
def register_user(username: str, password: str) -> str:
    """Создаёт пользователя и пустой портфель со стартовым капиталом."""
    if not username.strip():
        raise ValueError("Имя не может быть пустым")
    if len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    new_id_box: dict[str, int] = {}

    def _create_user(users: Any) -> list[dict[str, Any]]:
        users = users or []
        if any(u["username"] == username for u in users):
            raise ValueError(f"Имя пользователя '{username}' уже занято")
        new_id = max((u["user_id"] for u in users), default=0) + 1
        users.append(User.create(new_id, username, password).to_dict())
        new_id_box["id"] = new_id
        return users

    _db.transaction("users_file", _create_user)
    new_id = new_id_box["id"]

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


@log_action("LOGIN")
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
    get_currency(base)
    portfolio = _get_portfolio(user.user_id)
    if not portfolio.wallets:
        return f"Портфель пользователя '{user.username}' пуст"
    pairs = _db.read("rates_file", default={"pairs": {}}).get("pairs", {})
    lines = [f"Портфель пользователя '{user.username}' (база: {base}):"]
    total = 0.0
    for code, wallet in sorted(portfolio.wallets.items()):
        if code == base:
            value = wallet.balance
        else:
            entry = pairs.get(f"{code}_{base}")
            if entry is None:
                lines.append(
                    f"- {code}: {wallet.balance:.4f} → курс {code}→{base} недоступен"
                )
                continue
            value = wallet.balance * entry["rate"]
        total += value
        currency_obj = get_currency(code)
        lines.append(
            f"- {code}: {currency_obj.formatting(wallet.balance)} → {value:,.2f} {base}"
        )

    lines.append("-" * 33)
    lines.append(f"ИТОГО: {total:,.2f} {base}")
    return "\n".join(lines)


def _cache_rate(pair: str, rate: float, updated_at: str) -> None:
    """Сохраняет курс в rates.json через безопасную транзакцию."""

    def _update(data: Any) -> dict[str, Any]:
        data = data or {"pairs": {}, "last_refresh": None}
        data.setdefault("pairs", {})[pair] = {
            "rate": rate,
            "updated_at": updated_at,
            "source": "Stub",
        }
        data["last_refresh"] = updated_at
        return data

    _db.transaction("rates_file", _update, default={"pairs": {}, "last_refresh": None})


def get_rate(from_code: str, to_code: str) -> tuple[float, str]:
    """Возвращает (курс, время обновления), при необходимости из заглушки."""
    from_code = validate_currency_code(from_code)
    to_code = validate_currency_code(to_code)
    get_currency(from_code)  # бросит CurrencyNotFoundError, если валюта неизвестна
    get_currency(to_code)
    if from_code == to_code:
        return 1.0, datetime.now().isoformat(timespec="seconds")

    pair = f"{from_code}_{to_code}"
    entry = _db.read("rates_file", default={"pairs": {}}).get("pairs", {}).get(pair)
    ttl = _settings.get("rates_ttl_seconds", 300)
    if entry is not None:
        updated = datetime.fromisoformat(entry["updated_at"])
        age = (datetime.now() - updated).total_seconds()
        if age <= ttl:
            return float(entry["rate"]), entry["updated_at"]

    # Кеш отсутствует или устарел (TTL из SettingsLoader) - обновляем из заглушки
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
    _cache_rate(pair, rate, updated_at)
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


@log_action("BUY")
def _buy(user_id: int, currency_code: str, amount: float) -> str:
    """Внутренняя покупка: уже залогиненный пользователь."""
    currency_code = validate_currency_code(currency_code)
    amount = validate_amount(amount)
    get_currency(currency_code)

    portfolio = _get_portfolio(user_id)
    if currency_code == "USD":
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

    rate, _ = get_rate(currency_code, "USD")
    cost = amount * rate
    usd_wallet = portfolio.get_wallet("USD")
    if usd_wallet is None:
        usd_wallet = portfolio.add_currency("USD")
    if usd_wallet.balance < cost:
        raise InsufficientFundsError(usd_wallet.balance, cost, "USD")
    usd_wallet.withdraw(cost)

    wallet = portfolio.get_wallet(currency_code)
    was = wallet.balance if wallet is not None else 0.0
    if wallet is None:
        wallet = portfolio.add_currency(currency_code)
    wallet.deposit(amount)
    _save_portfolio(portfolio)
    return (
        f"Покупка выполнена: {amount:.4f} {currency_code} "
        f"по курсу {rate:,.2f} USD/{currency_code}\n"
        f"Изменения в портфеле:\n"
        f"- {currency_code}: было {was:.4f} → стало {wallet.balance:.4f}\n"
        f"Оценочная стоимость покупки: {cost:,.2f} USD"
    )


def buy_currency(currency: str, amount: float) -> str:
    """Покупает валюту за USD по текущему курсу (контракт CLI)."""
    user = require_login()
    return _buy(user.user_id, currency, amount)


@log_action("SELL")
def _sell(user_id: int, currency_code: str, amount: float) -> str:
    """Внутренняя продажа: уже залогиненный пользователь."""
    currency_code = validate_currency_code(currency_code)
    amount = validate_amount(amount)
    get_currency(currency_code)

    portfolio = _get_portfolio(user_id)
    wallet = portfolio.get_wallet(currency_code)
    if wallet is None:
        raise ValueError(
            f"У вас нет кошелька '{currency_code}'. Добавьте валюту: "
            f"она создаётся автоматически при первой покупке."
        )
    if wallet.balance < amount:
        raise InsufficientFundsError(wallet.balance, amount, currency_code)

    was = wallet.balance
    wallet.withdraw(amount)
    if currency_code == "USD":
        revenue = amount
    else:
        revenue = amount * get_rate(currency_code, "USD")[0]
        usd_wallet = portfolio.get_wallet("USD")
        if usd_wallet is None:
            usd_wallet = portfolio.add_currency("USD")
        usd_wallet.deposit(revenue)
    _save_portfolio(portfolio)
    return (
        f"Продажа выполнена: {amount:.4f} {currency_code}\n"
        f"Изменения в портфеле:\n"
        f"- {currency_code}: было {was:.4f} → стало {wallet.balance:.4f}\n"
        f"Оценочная выручка: {revenue:,.2f} USD"
    )


def sell_currency(currency: str, amount: float) -> str:
    """Продаёт валюту за USD по текущему курсу (контракт CLI)."""
    user = require_login()
    return _sell(user.user_id, currency, amount)
