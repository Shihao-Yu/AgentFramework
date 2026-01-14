"""Auth providers."""

from contextforge.providers.auth.header import HeaderAuthProvider
from contextforge.providers.auth.noop import NoopAuthProvider

def __getattr__(name):
    if name == "JWTAuthProvider":
        from contextforge.providers.auth.jwt import JWTAuthProvider
        return JWTAuthProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "HeaderAuthProvider",
    "NoopAuthProvider",
    "JWTAuthProvider",
]
