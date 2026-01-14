import os
import pytest
from pathlib import Path
from unittest.mock import patch

from infra.settings.ssl import SSLSettings, get_ssl_settings


class TestSSLSettings:

    def test_default_cert_path_points_to_certs_dir(self):
        path = SSLSettings.default_cert_path()
        assert path.name == "cacert.pem"
        assert "certs" in str(path)

    def test_get_ca_cert_raises_when_cert_missing(self):
        settings = SSLSettings(ca_cert_path="/nonexistent/path/cert.pem")
        
        with pytest.raises(FileNotFoundError) as exc_info:
            settings.get_ca_cert()
        
        assert "SSL CA certificate required" in str(exc_info.value)

    def test_get_ca_cert_returns_path_when_exists(self, tmp_path):
        cert_file = tmp_path / "test_cert.pem"
        cert_file.write_text("FAKE CERT CONTENT")
        
        settings = SSLSettings(ca_cert_path=str(cert_file))
        result = settings.get_ca_cert()
        
        assert result == str(cert_file.resolve())

    def test_get_ca_cert_or_none_returns_none_when_missing(self):
        settings = SSLSettings(ca_cert_path="/nonexistent/path/cert.pem")
        result = settings.get_ca_cert_or_none()
        
        assert result is None

    def test_get_ca_cert_or_none_returns_path_when_exists(self, tmp_path):
        cert_file = tmp_path / "test_cert.pem"
        cert_file.write_text("FAKE CERT CONTENT")
        
        settings = SSLSettings(ca_cert_path=str(cert_file))
        result = settings.get_ca_cert_or_none()
        
        assert result == str(cert_file.resolve())

    def test_env_var_override(self, tmp_path):
        cert_file = tmp_path / "env_cert.pem"
        cert_file.write_text("FAKE CERT CONTENT")
        
        with patch.dict(os.environ, {"SSL_CA_CERT_PATH": str(cert_file)}):
            settings = SSLSettings()
            result = settings.get_ca_cert()
        
        assert result == str(cert_file.resolve())


class TestGetSSLSettings:

    def test_returns_singleton(self):
        import infra.settings.ssl as ssl_module
        ssl_module._ssl_settings = None
        
        settings1 = get_ssl_settings()
        settings2 = get_ssl_settings()
        
        assert settings1 is settings2
        
        ssl_module._ssl_settings = None
