"""Модели данных: User, Wallet, Portfolio."""

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any


def _hash_password(password: str, salt: str) -> str:
    """Возвращает хеш пароля с солью."""
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


class User:
    """Пользователь с приватными атрибутами и валидацией."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        """Инициализирует пользователя."""
        self._user_id = user_id
        self.username = username  # через сеттер — сработает проверка
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @classmethod
    def create(cls, user_id: int, username: str, password: str) -> User:
        """Создаёт нового пользователя: генерирует соль и хеширует пароль."""
        if len(password) < 4:
            raise ValueError("Пароль от 4 символов")
        salt = secrets.token_hex(8)
        return cls(
            user_id=user_id,
            username=username,
            hashed_password=_hash_password(password, salt),
            salt=salt,
            registration_date=datetime.now(UTC),
        )

    # --- геттеры/сеттеры ---

    @property
    def user_id(self) -> int:
        """Уникальный идентификатор пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Имя пользователя."""
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        """Проверяет, что имя непустое."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя не может быть пустым")
        self._username = value

    @property
    def registration_date(self) -> datetime:
        """Дата регистрации пользователя."""
        return self._registration_date

    # методы

    def get_user_info(self) -> str:
        """Возвращает информацию о пользователе."""
        return (
            f"Пользователь '{self._username}' (id={self._user_id}), "
            f"зарегистрирован: {self._registration_date.isoformat()}"
        )

    def change_password(self, new_password: str) -> None:
        """Изменяет пароль."""
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        self._salt = secrets.token_hex(8)  # новая соль
        self._hashed_password = _hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """Проверяет введённый пароль на совпадение с хешем."""
        return _hash_password(password, self._salt) == self._hashed_password

    # сериализация в JSON

    def to_dict(self) -> dict[str, Any]:
        """Сериализует пользователя для users.json."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> User:
        """Восстанавливает пользователя из словаря users.json."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"]),
        )


class Wallet:
    """Кошелёк пользователя для одной конкретной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        """Создаёт кошелёк с кодом валюты и начальным балансом."""
        self.currency_code = currency_code
        self.balance = balance  # через сеттер — сработает проверка

    @staticmethod
    def _check_amount(amount: Any) -> None:
        """Проверяет, что сумма — положительное число."""
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise TypeError("Сумма должна быть числом")
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")

    # свойство balance

    @property
    def balance(self) -> float:
        """Текущий баланс кошелька."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        """Запрещает отрицательные и некорректные значения баланса."""
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """Пополняет баланс на положительную сумму."""
        self._check_amount(amount)
        self._balance += float(amount)

    def withdraw(self, amount: float) -> None:
        """Снимает средства, проверяя достаточность баланса."""
        self._check_amount(amount)
        if amount > self._balance:
            raise ValueError(
                f"Недостаточно средств: доступно {self._balance:.4f} "
                f"{self.currency_code}, требуется {amount:.4f} {self.currency_code}"
            )
        self._balance -= float(amount)

    def get_balance_info(self) -> str:
        """Возвращает информацию о текущем балансе."""
        return f"{self.currency_code}: {self._balance:.4f}"

    # сериализация

    def to_dict(self) -> dict[str, Any]:
        """Сериализует кошелёк для portfolios.json."""
        return {"currency_code": self.currency_code, "balance": self._balance}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Wallet:
        """Восстанавливает кошелёк из словаря."""
        return cls(currency_code=data["currency_code"], balance=data["balance"])


class Portfolio:
    """Управляет всеми кошельками одного пользователя."""

    def __init__(self, user_id: int, wallets: dict[str, Wallet] | None = None) -> None:
        """Создаёт портфель пользователя (пустой по умолчанию)."""
        self._user_id = user_id
        self._wallets: dict[str, Wallet] = wallets if wallets is not None else {}

    @property
    def user_id(self) -> int:
        """Идентификатор пользователя."""
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Возвращает копию словаря кошельков (защита от мутаций)."""
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        """Добавляет новый кошелёк, проверяя уникальность кода валюты."""
        currency_code = currency_code.strip().upper()
        if not currency_code:
            raise ValueError("Код валюты не может быть пустым")
        if currency_code in self._wallets:
            raise ValueError(f"Кошелёк '{currency_code}' уже существует")
        wallet = Wallet(currency_code, 0.0)
        self._wallets[currency_code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Wallet:
        """Возвращает кошелёк по коду валюты или None, если его нет."""
        return self._wallets.get(currency_code.strip().upper())

    def get_total_value(
        self, rates: dict[str, float], base_currency: str = "USD"
    ) -> float:
        """Считает общую стоимость всех валют"""
        total = 0.0
        for code, wallet in self._wallets.items():
            if code == base_currency:
                total += wallet.balance
            else:
                pair = f"{code}_{base_currency}"
                rate = rates.get(pair)
                if rate is not None:
                    total += wallet.balance * rate
        return total

    # сериализация

    def to_dict(self) -> dict[str, Any]:
        """Сериализует портфель для portfolios.json."""
        return {
            "user_id": self._user_id,
            "wallets": {code: w.to_dict() for code, w in self._wallets.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Portfolio:
        """Восстанавливает портфель из словаря portfolios.json."""
        wallets = {
            code: Wallet(currency_code=code, balance=w["balance"])
            for code, w in data.get("wallets", {}).items()
        }
        return cls(user_id=data["user_id"], wallets=wallets)
