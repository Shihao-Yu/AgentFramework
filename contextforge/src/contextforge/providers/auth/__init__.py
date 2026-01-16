"""Auth providers."""

from contextforge.providers.auth.header import HeaderAuthProvider
from contextforge.providers.auth.noop import NoopAuthProvider


def __getattr__(name: str):
    lazy_imports = {
        "JWTAuthProvider": "contextforge.providers.auth.jwt",
        "JWKSAuthProvider": "contextforge.providers.auth.jwks",
        "JWTValidationResult": "contextforge.providers.auth.jwks",
    }
    
    if name in lazy_imports:
        module = __import__(lazy_imports[name], fromlist=[name])
        return getattr(module, name)
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "HeaderAuthProvider",
    "NoopAuthProvider",
    "JWTAuthProvider",
    "JWKSAuthProvider",
    "JWTValidationResult",
]
