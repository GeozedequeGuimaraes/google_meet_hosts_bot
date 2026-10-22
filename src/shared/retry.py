"""
Retry com backoff exponencial e jitter para chamadas à Google API.

Distingue erros transitórios (rate limit, timeout, 5xx) de erros de negócio
(4xx, credenciais inválidas) — só retenta os primeiros.
"""

import logging
import random
import time
from functools import wraps
from typing import Callable, Tuple, Type

logger = logging.getLogger(__name__)

# Erros que justificam retry (transitórios)
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def _is_retryable(exc: Exception) -> bool:
    try:
        from googleapiclient.errors import HttpError  # type: ignore
        if isinstance(exc, HttpError):
            return int(exc.resp.status) in _RETRYABLE_STATUS
    except ImportError:
        pass
    # ConnectionError, TimeoutError e similares também são transitórios
    return isinstance(exc, (ConnectionError, TimeoutError, OSError))


def with_backoff(
    *,
    max_attempts: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorator que retenta a função com backoff exponencial + jitter.

    Args:
        max_attempts: número máximo de tentativas (incluindo a primeira).
        base_delay: delay inicial em segundos.
        max_delay: teto do delay em segundos.
        exceptions: tipos de exceção que acionam retry.
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc: Exception = RuntimeError("sem tentativas")
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if not _is_retryable(exc):
                        raise
                    if attempt == max_attempts:
                        break
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    jitter = random.uniform(0, delay * 0.25)
                    total = delay + jitter
                    logger.warning(
                        "Tentativa %d/%d falhou (%s). Retry em %.1fs.",
                        attempt, max_attempts, type(exc).__name__, total,
                    )
                    time.sleep(total)
            raise last_exc
        return wrapper
    return decorator
