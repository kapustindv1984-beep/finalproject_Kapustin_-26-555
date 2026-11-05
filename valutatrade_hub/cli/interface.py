"""Командный интерфейс ValutaTrade Hub."""

import shlex

from valutatrade_hub.core import usecases
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)

HELP_TEXT = """Доступные команды:
  register --username NAME --password PASS  регистрация
  login --username NAME --password PASS     вход
  show-portfolio [--base CUR]               портфель и итог в базовой валюте
  buy --currency CUR --amount N             купить валюту за USD
  sell --currency CUR --amount N            продать валюту
  get-rate --from CUR1 --to CUR2            курс валютной пары
  help                                      этот список
  exit                                      выход"""


def _parse_args(args: list[str], required: tuple[str, ...]) -> dict[str, str]:
    values: dict[str, str] = {}
    i = 0
    while i < len(args):
        key = args[i]
        if not key.startswith("--") or i + 1 >= len(args):
            raise ValueError(f"Некорректный аргумент: '{key}'. Формат: --ключ значение")
        values[key[2:]] = args[i + 1]
        i += 2
    for req in required:
        if req not in values:
            raise ValueError(f"Не хватает обязательного аргумента: --{req}")
    return values


def _to_float(raw: str) -> float:
    try:
        return float(raw)
    except ValueError:
        raise ValueError("'amount' должен быть положительным числом") from None


def _dispatch(command: str, args: list[str]) -> None:
    if command == "help":
        print(HELP_TEXT)
    elif command == "register":
        v = _parse_args(args, ("username", "password"))
        print(usecases.register_user(v["username"], v["password"]))
    elif command == "login":
        v = _parse_args(args, ("username", "password"))
        print(usecases.login_user(v["username"], v["password"]))
    elif command == "show-portfolio":
        v = _parse_args(args, ())
        print(usecases.show_portfolio(v.get("base", "USD")))
    elif command == "buy":
        v = _parse_args(args, ("currency", "amount"))
        print(usecases.buy_currency(v["currency"], _to_float(v["amount"])))
    elif command == "sell":
        v = _parse_args(args, ("currency", "amount"))
        print(usecases.sell_currency(v["currency"], _to_float(v["amount"])))
    elif command == "get-rate":
        v = _parse_args(args, ("from", "to"))
        print(usecases.get_rate_message(v["from"], v["to"]))
    else:
        print(f"Неизвестная команда: '{command}'. Введите 'help'")


def main() -> None:
    print("ValutaTrade Hub. Введите 'help' для списка команд.")
    while True:
        try:
            raw = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            return
        if not raw:
            continue
        parts = shlex.split(raw)
        command, args = parts[0], parts[1:]
        if command == "exit":
            print("Bye!")
            return
        try:
            _dispatch(command, args)
        except (InsufficientFundsError, ApiRequestError) as e:
            print(f"Ошибка: {e}")
        except CurrencyNotFoundError as e:
            print(f"Ошибка: {e}")
            print("Поддерживаемые коды: USD, EUR, GBP, RUB, BTC, ETH, SOL")
        except (PermissionError, ValueError, TypeError) as e:
            print(f"Ошибка: {e}")
