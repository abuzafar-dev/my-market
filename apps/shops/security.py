"""Brute-force protection for logging in.

Two counters live in the cache:
  * per (IP, phone): 5 wrong passwords lock that pair for 15 minutes, so a guesser
    is stopped fast while the real owner, coming from another IP, is not;
  * per phone alone: 30 wrong passwords in an hour lock the phone for an hour,
    which stops one number being attacked from many addresses.
A correct password clears the per-pair counter. The same backend guards the
Django admin login, which uses ``authenticate()`` too.

The cache must be shared by all gunicorn workers (prod uses a file cache; see
config/settings/prod.py) or every worker would count on its own."""

from django.contrib.auth.backends import ModelBackend
from django.core.cache import cache
from rest_framework.throttling import BaseThrottle

PAIR_LIMIT, PAIR_WINDOW = 5, 15 * 60
PHONE_LIMIT, PHONE_WINDOW = 30, 60 * 60


def client_ip(request) -> str:
    """The caller's address, honouring REST_FRAMEWORK["NUM_PROXIES"] so a spoofed
    X-Forwarded-For can't be used to dodge the limits."""
    return BaseThrottle().get_ident(request)


def _keys(request, phone: str) -> tuple[str, str]:
    return f"login-fail:{client_ip(request)}:{phone}", f"login-fail-phone:{phone}"


def is_locked(request, phone: str) -> bool:
    pair_key, phone_key = _keys(request, phone)
    return cache.get(pair_key, 0) >= PAIR_LIMIT or cache.get(phone_key, 0) >= PHONE_LIMIT


def _bump(key: str, window: int) -> None:
    # add() only sets a missing key, so the window starts at the first failure.
    cache.add(key, 0, window)
    try:
        cache.incr(key)
    except ValueError:  # expired between add() and incr()
        cache.set(key, 1, window)


def record_failure(request, phone: str) -> None:
    pair_key, phone_key = _keys(request, phone)
    _bump(pair_key, PAIR_WINDOW)
    _bump(phone_key, PHONE_WINDOW)


def clear_failures(request, phone: str) -> None:
    cache.delete(_keys(request, phone)[0])


class LockoutModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if request is None or not username:
            return super().authenticate(request, username, password, **kwargs)
        if is_locked(request, username):
            return None
        user = super().authenticate(request, username, password, **kwargs)
        if user is None:
            record_failure(request, username)
        else:
            clear_failures(request, username)
        return user
