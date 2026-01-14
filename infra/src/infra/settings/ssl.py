"""SSL certificate settings for clients that require custom CA certs."""

from pathlib import Path
from typing import Optional

from infra.settings.base import BaseAppSettings


class SSLSettings(BaseAppSettings):
    """SSL settings for inference, embedding, and tracing clients.

    The CA certificate is required for these clients. By default, it looks for
    the cert at infra/certs/cacert.pem. Override with SSL_CA_CERT_PATH env var.
    """

    ca_cert_path: Optional[str] = None

    model_config = {"env_prefix": "SSL_"}

    @classmethod
    def default_cert_path(cls) -> Path:
        return Path(__file__).parent.parent.parent / "certs" / "cacert.pem"

    def get_ca_cert(self) -> str:
        """Return cert path, raising FileNotFoundError if missing.

        Raises:
            FileNotFoundError: If cert file does not exist.
        """
        if self.ca_cert_path:
            path = Path(self.ca_cert_path)
        else:
            path = self.default_cert_path()

        if not path.exists():
            raise FileNotFoundError(
                f"SSL CA certificate required but not found: {path}\n"
                "Set SSL_CA_CERT_PATH env var or add cert to infra/certs/cacert.pem"
            )
        return str(path.resolve())

    def get_ca_cert_or_none(self) -> Optional[str]:
        """Return cert path if exists, None otherwise.

        Use this for optional SSL verification (e.g., local development).
        """
        if self.ca_cert_path:
            path = Path(self.ca_cert_path)
        else:
            path = self.default_cert_path()

        if path.exists():
            return str(path.resolve())
        return None


_ssl_settings: Optional[SSLSettings] = None


def get_ssl_settings() -> SSLSettings:
    """Get singleton SSL settings instance."""
    global _ssl_settings
    if _ssl_settings is None:
        _ssl_settings = SSLSettings()
    return _ssl_settings
