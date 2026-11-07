"""Командный интерфейс ValutaTrade Hub."""

import shlex

from valutatrade_hub.core import usecases
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)

HELP_TEXT = """Доступные команды:
  register --username NAME --password PASS              регистрация
  login --username NAME --password PASS                 вход
  show-portfolio [--base CUR]                           портфель и итог в базовой валюте
  buy --currency CUR --amount N                         купить валюту за USD
  sell --currency CUR --amount N                        продать валюту
  get-rate --from CUR1 --to CUR2                        курс валютной пары
  update-rates [--source coingecko|exchangerate]        обновить курсы из API
  show-rates [--currency CUR] [--top N] [--base CUR]    курсы из кеша таблицей

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
    elif command == "update-rates":
        v = _parse_args(args, ())
        cmd_update_rates(v)
    elif command == "show-rates":
        v = _parse_args(args, ())
        cmd_show_rates(v)
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

def cmd_update_rates(args: dict) -> None:
    """Запускает обновление курсов из внешних API."""
    from valutatrade_hub.parser_service.updater import RatesUpdater

    updater = RatesUpdater()
    summary = updater.run_update(source=args.get("source"))

    if summary["updated"] == 0:
        print("Update completed with errors. Check logs/parser.log for details.")
        return
    print(
        f"Update successful. Total rates updated: {summary['updated']}. "
        f"Last refresh: {summary['last_refresh']}"
    )
    if summary["errors"]:
        print("Но были ошибки по части источников:", "; ".join(summary["errors"]))

def cmd_show_rates(args: dict) -> None:
    """Показывает курсы из локального кеша с фильтрацией."""
    from prettytable import PrettyTable

    from valutatrade_hub.parser_service import storage

    cache = storage.read_cache()
    pairs = cache.get("pairs", {})
    if not pairs:
        print("Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные.")
        return

    currency = (args.get("currency") or "").upper()
    base = (args.get("base") or "USD").upper()
    top = args.get("top")

    rows: list[tuple[str, float]] = []
    for pair, info in pairs.items():
        if currency and not pair.startswith(currency + "_"):
            continue
        if base != "USD":
            # Пересчёт в произвольную базу через USD:
            # rate(A_EUR) = rate(A_USD) / rate(EUR_USD)
            base_usd = pairs.get(f"{base}_USD")
            if base_usd is None:
                print(f"Неизвестная базовая валюта '{base}'")
                return
            rows.append((f"{pair.split('_')[0]}_{base}", info["rate"] / base_usd["rate"]))
        else:
            rows.append((pair, info["rate"]))

    if not rows:
        print(f"Курс для '{currency}' не найден в кеше.")
        return

    if top is not None:
        crypto_codes = ("BTC", "ETH", "SOL")

        rows = sorted(
            (r for r in rows if r[0].split("_")[0] in crypto_codes),
            key=lambda r: r[1],
            reverse=True,
        )[:int(top)]
    else:
        rows.sort(key=lambda r: r[0])

    updated = cache.get("last_refresh") or "?"
    print(f"Rates from cache (updated at {updated}):")
    table = PrettyTable()
    table.field_names = ["Pair", "Rate"]
    for pair, rate in rows:
        table.add_row([pair, f"{rate:.6f}"])
    print(table)
