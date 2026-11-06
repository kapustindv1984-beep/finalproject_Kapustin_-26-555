"""Декоратор @log_action: логирование доменных операций buy/sell и др."""

import functools
import inspect
from collections.abc import Callable
from typing import Any

from valutatrade_hub.logging_config import setup_logging


def _format_num(value: Any) -> str:
    """Числа - с четырьмя знаками."""
    if isinstance(value, (int, float)):
        return f"{value:.4f}"
    return str(value)


def log_action(action: str, verbose: bool = False) -> Callable:
    """Оборачивает функцию usecases в логирующую.

    action - имя операции (BUY/SELL/REGISTER/LOGIN).
    verbose - добавить в лог дополнительные параметры вызова
    (состояние кошелька «было→стало»).
    """

    def decorator(func: Callable) -> Callable:
        logger = setup_logging()

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = inspect.signature(func).bind(*args, **kwargs)
            bound.apply_defaults()
            params = bound.arguments

            user = params.get("username") or params.get("user_id") or "?"
            parts = [f"{action} user={user!r}"]
            if "currency_code" in params:
                parts.append(f"currency={params['currency_code']!r}")
            if params.get("amount") is not None:
                parts.append(f"amount={_format_num(params['amount'])}")
            if params.get("rate") is not None:
                parts.append(f"rate={_format_num(params['rate'])}")
            if params.get("base") is not None:
                parts.append(f"base={params['base']!r}")
            if verbose:
                extra = {
                    k: _format_num(v)
                    for k, v in params.items()
                    if k not in {"user_id", "username", "currency_code", "amount"}
                    and not k.startswith("_")
                }
                if extra:
                    parts.append(f"context={extra}")

            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                parts.append(f"result=ERROR error_type={type(exc).__name__} "
                             f"error_message={exc!s}")
                logger.error(" ".join(parts))
                raise
            parts.append("result=OK")
            logger.info(" ".join(parts))
            return result

        return wrapper

    return decorator
