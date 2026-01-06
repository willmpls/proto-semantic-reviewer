"""
Tests for adapter configuration: custom endpoints, headers, and CA certificates.
"""

import os
import ssl
import pytest
from unittest.mock import patch, MagicMock

from src.adapters.base import (
    get_provider_headers,
    get_ca_bundle,
    get_base_url,
    create_ssl_context,
)


class TestGetProviderHeaders:
    """Tests for get_provider_headers() function."""

    def test_no_headers_set(self):
        """Test when no headers are configured."""
        with patch.dict(os.environ, {}, clear=True):
            headers = get_provider_headers("OPENAI")
            assert headers == {}

    def test_single_header(self):
        """Test parsing a single header."""
        with patch.dict(os.environ, {"OPENAI_HEADER_X_Request_Id": "123"}, clear=True):
            headers = get_provider_headers("OPENAI")
            assert headers == {"X-Request-Id": "123"}

    def test_multiple_headers(self):
        """Test parsing multiple headers for same provider."""
        env = {
            "OPENAI_HEADER_X_Request_Id": "123",
            "OPENAI_HEADER_X_Tenant_Id": "tenant-abc",
            "OPENAI_HEADER_Authorization": "Bearer token",
        }
        with patch.dict(os.environ, env, clear=True):
            headers = get_provider_headers("OPENAI")
            assert headers == {
                "X-Request-Id": "123",
                "X-Tenant-Id": "tenant-abc",
                "Authorization": "Bearer token",
            }

    def test_underscore_to_hyphen_conversion(self):
        """Test that single underscores in header names become hyphens."""
        with patch.dict(os.environ, {"ANTHROPIC_HEADER_X_Custom_Auth_Token": "secret"}, clear=True):
            headers = get_provider_headers("ANTHROPIC")
            assert headers == {"X-Custom-Auth-Token": "secret"}

    def test_double_underscore_to_literal_underscore(self):
        """Test that double underscores become literal underscores."""
        with patch.dict(os.environ, {"OPENAI_HEADER_X__Custom__Name": "value"}, clear=True):
            headers = get_provider_headers("OPENAI")
            assert headers == {"X_Custom_Name": "value"}

    def test_mixed_underscore_patterns(self):
        """Test mixed single and double underscores."""
        with patch.dict(os.environ, {"OPENAI_HEADER_X_Foo__Bar_Baz": "value"}, clear=True):
            headers = get_provider_headers("OPENAI")
            assert headers == {"X-Foo_Bar-Baz": "value"}

    def test_different_providers_isolated(self):
        """Test that headers are isolated per provider."""
        env = {
            "OPENAI_HEADER_X_OpenAI": "openai-value",
            "ANTHROPIC_HEADER_X_Anthropic": "anthropic-value",
        }
        with patch.dict(os.environ, env, clear=True):
            openai_headers = get_provider_headers("OPENAI")
            anthropic_headers = get_provider_headers("ANTHROPIC")

            assert openai_headers == {"X-OpenAI": "openai-value"}
            assert anthropic_headers == {"X-Anthropic": "anthropic-value"}

    def test_empty_header_value(self):
        """Test header with empty value."""
        with patch.dict(os.environ, {"OPENAI_HEADER_X_Empty": ""}, clear=True):
            headers = get_provider_headers("OPENAI")
            assert headers == {"X-Empty": ""}

    def test_case_sensitivity(self):
        """Test that provider prefix is case-sensitive."""
        with patch.dict(os.environ, {"openai_HEADER_X_Lower": "value"}, clear=True):
            headers = get_provider_headers("OPENAI")
            assert headers == {}  # Should not match lowercase prefix


class TestGetCaBundle:
    """Tests for get_ca_bundle() function."""

    def test_no_ca_bundle_set(self):
        """Test when no CA bundle is configured."""
        with patch.dict(os.environ, {}, clear=True):
            bundle = get_ca_bundle("OPENAI")
            assert bundle is None

    def test_provider_specific_ca_bundle(self, tmp_path):
        """Test provider-specific CA bundle."""
        ca_file = tmp_path / "openai-ca.pem"
        ca_file.write_text("cert content")
        with patch.dict(os.environ, {"OPENAI_CA_BUNDLE": str(ca_file)}, clear=True):
            bundle = get_ca_bundle("OPENAI")
            assert bundle == str(ca_file)

    def test_fallback_to_llm_ca_bundle(self, tmp_path):
        """Test fallback to LLM_CA_BUNDLE when provider-specific not set."""
        ca_file = tmp_path / "default-ca.pem"
        ca_file.write_text("cert content")
        with patch.dict(os.environ, {"LLM_CA_BUNDLE": str(ca_file)}, clear=True):
            bundle = get_ca_bundle("OPENAI")
            assert bundle == str(ca_file)

    def test_provider_specific_takes_precedence(self, tmp_path):
        """Test that provider-specific CA bundle takes precedence over fallback."""
        openai_ca = tmp_path / "openai-ca.pem"
        openai_ca.write_text("cert content")
        default_ca = tmp_path / "default-ca.pem"
        default_ca.write_text("cert content")
        env = {
            "OPENAI_CA_BUNDLE": str(openai_ca),
            "LLM_CA_BUNDLE": str(default_ca),
        }
        with patch.dict(os.environ, env, clear=True):
            bundle = get_ca_bundle("OPENAI")
            assert bundle == str(openai_ca)

    def test_different_providers_different_bundles(self, tmp_path):
        """Test different CA bundles for different providers."""
        openai_ca = tmp_path / "openai-ca.pem"
        openai_ca.write_text("cert content")
        anthropic_ca = tmp_path / "anthropic-ca.pem"
        anthropic_ca.write_text("cert content")
        default_ca = tmp_path / "default-ca.pem"
        default_ca.write_text("cert content")
        env = {
            "OPENAI_CA_BUNDLE": str(openai_ca),
            "ANTHROPIC_CA_BUNDLE": str(anthropic_ca),
            "LLM_CA_BUNDLE": str(default_ca),
        }
        with patch.dict(os.environ, env, clear=True):
            assert get_ca_bundle("OPENAI") == str(openai_ca)
            assert get_ca_bundle("ANTHROPIC") == str(anthropic_ca)
            assert get_ca_bundle("GEMINI") == str(default_ca)  # Falls back

    def test_fallback_to_ssl_cert_file(self, tmp_path):
        """Test fallback to SSL_CERT_FILE (standard OpenSSL env var)."""
        ca_file = tmp_path / "ca-certificates.crt"
        ca_file.write_text("cert content")
        with patch.dict(os.environ, {"SSL_CERT_FILE": str(ca_file)}, clear=True):
            bundle = get_ca_bundle("OPENAI")
            assert bundle == str(ca_file)

    def test_fallback_to_requests_ca_bundle(self, tmp_path):
        """Test fallback to REQUESTS_CA_BUNDLE."""
        ca_file = tmp_path / "ca-bundle.crt"
        ca_file.write_text("cert content")
        with patch.dict(os.environ, {"REQUESTS_CA_BUNDLE": str(ca_file)}, clear=True):
            bundle = get_ca_bundle("OPENAI")
            assert bundle == str(ca_file)

    def test_ssl_cert_file_precedence_over_requests(self, tmp_path):
        """Test SSL_CERT_FILE takes precedence over REQUESTS_CA_BUNDLE."""
        ssl_cert = tmp_path / "ssl-cert.pem"
        ssl_cert.write_text("cert content")
        requests_ca = tmp_path / "requests-ca.pem"
        requests_ca.write_text("cert content")
        env = {
            "SSL_CERT_FILE": str(ssl_cert),
            "REQUESTS_CA_BUNDLE": str(requests_ca),
        }
        with patch.dict(os.environ, env, clear=True):
            bundle = get_ca_bundle("OPENAI")
            assert bundle == str(ssl_cert)

    def test_llm_ca_bundle_precedence_over_standard_vars(self, tmp_path):
        """Test LLM_CA_BUNDLE takes precedence over SSL_CERT_FILE and REQUESTS_CA_BUNDLE."""
        llm_ca = tmp_path / "llm-ca.pem"
        llm_ca.write_text("cert content")
        ssl_cert = tmp_path / "ssl-cert.pem"
        ssl_cert.write_text("cert content")
        requests_ca = tmp_path / "requests-ca.pem"
        requests_ca.write_text("cert content")
        env = {
            "LLM_CA_BUNDLE": str(llm_ca),
            "SSL_CERT_FILE": str(ssl_cert),
            "REQUESTS_CA_BUNDLE": str(requests_ca),
        }
        with patch.dict(os.environ, env, clear=True):
            bundle = get_ca_bundle("OPENAI")
            assert bundle == str(llm_ca)

    def test_nonexistent_path_is_skipped(self):
        """Test that non-existent CA bundle paths are skipped."""
        env = {
            "OPENAI_CA_BUNDLE": "/nonexistent/path.pem",
            "SSL_CERT_FILE": "/also/nonexistent.pem",
        }
        with patch.dict(os.environ, env, clear=True):
            bundle = get_ca_bundle("OPENAI")
            assert bundle is None

    def test_falls_back_to_existing_file(self, tmp_path):
        """Test fallback to next candidate when first doesn't exist."""
        existing_ca = tmp_path / "existing-ca.pem"
        existing_ca.write_text("cert content")
        env = {
            "OPENAI_CA_BUNDLE": "/nonexistent/path.pem",
            "LLM_CA_BUNDLE": str(existing_ca),
        }
        with patch.dict(os.environ, env, clear=True):
            bundle = get_ca_bundle("OPENAI")
            assert bundle == str(existing_ca)


class TestGetBaseUrl:
    """Tests for get_base_url() function."""

    def test_no_base_url_set(self):
        """Test when no base URL is configured."""
        with patch.dict(os.environ, {}, clear=True):
            url = get_base_url("OPENAI")
            assert url is None

    def test_provider_specific_base_url(self):
        """Test provider-specific base URL."""
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://proxy.example.com/v1"}, clear=True):
            url = get_base_url("OPENAI")
            assert url == "https://proxy.example.com/v1"

    def test_different_providers_different_urls(self):
        """Test different base URLs for different providers."""
        env = {
            "OPENAI_BASE_URL": "https://openai-proxy.example.com",
            "ANTHROPIC_BASE_URL": "https://anthropic-proxy.example.com",
        }
        with patch.dict(os.environ, env, clear=True):
            assert get_base_url("OPENAI") == "https://openai-proxy.example.com"
            assert get_base_url("ANTHROPIC") == "https://anthropic-proxy.example.com"
            assert get_base_url("GEMINI") is None


class TestCreateSslContext:
    """Tests for create_ssl_context() function."""

    def test_no_ca_bundle_returns_true(self):
        """Test that None ca_bundle returns True (default verification)."""
        result = create_ssl_context(None)
        assert result is True

    def test_with_ca_bundle_returns_ssl_context(self, tmp_path):
        """Test that valid ca_bundle returns SSLContext."""
        # Create a temporary CA file (empty, but exists)
        ca_file = tmp_path / "ca-bundle.pem"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")

        # Note: This will fail with a real SSL context because the cert is invalid,
        # but we can at least test the function attempts to create a context
        with pytest.raises(ssl.SSLError):
            # Invalid cert content will raise SSLError
            create_ssl_context(str(ca_file))

    def test_nonexistent_ca_bundle_raises_error(self):
        """Test that non-existent ca_bundle raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            create_ssl_context("/nonexistent/path/to/ca.pem")


class TestAnthropicAdapterConfiguration:
    """Tests for AnthropicAdapter initialization with custom configuration."""

    def test_default_initialization(self):
        """Test adapter initializes with defaults when no custom config."""
        import sys
        mock_anthropic = MagicMock()
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            with patch.dict(os.environ, {}, clear=True):
                # Need to reload the module to pick up the mocked import
                import importlib
                import src.adapters.anthropic_adapter as adapter_module
                importlib.reload(adapter_module)

                adapter = adapter_module.AnthropicAdapter(api_key="test-key")

                mock_anthropic.Anthropic.assert_called_once_with(
                    api_key="test-key",
                    base_url=None,
                    http_client=None,
                )

    def test_with_custom_base_url(self):
        """Test adapter uses custom base URL."""
        import sys
        mock_anthropic = MagicMock()
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            env = {"ANTHROPIC_BASE_URL": "https://proxy.example.com"}
            with patch.dict(os.environ, env, clear=True):
                import importlib
                import src.adapters.anthropic_adapter as adapter_module
                importlib.reload(adapter_module)

                adapter = adapter_module.AnthropicAdapter(api_key="test-key")

                call_kwargs = mock_anthropic.Anthropic.call_args[1]
                assert call_kwargs["base_url"] == "https://proxy.example.com"

    @patch("src.adapters.anthropic_adapter.httpx.Client")
    def test_with_custom_headers(self, mock_httpx_client):
        """Test adapter creates httpx client with custom headers."""
        import sys
        mock_anthropic = MagicMock()
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            env = {
                "ANTHROPIC_HEADER_X_Custom": "value",
                "ANTHROPIC_HEADER_X_Another": "value2",
            }
            with patch.dict(os.environ, env, clear=True):
                import importlib
                import src.adapters.anthropic_adapter as adapter_module
                importlib.reload(adapter_module)

                adapter = adapter_module.AnthropicAdapter(api_key="test-key")

                # httpx.Client should be called with headers
                mock_httpx_client.assert_called_once()
                call_kwargs = mock_httpx_client.call_args[1]
                assert call_kwargs["headers"] == {"X-Custom": "value", "X-Another": "value2"}


class TestOpenAIAdapterConfiguration:
    """Tests for OpenAIAdapter initialization with custom configuration."""

    def test_default_initialization(self):
        """Test adapter initializes with defaults when no custom config."""
        import sys
        mock_openai_module = MagicMock()
        mock_OpenAI = MagicMock()
        mock_openai_module.OpenAI = mock_OpenAI
        with patch.dict(sys.modules, {"openai": mock_openai_module}):
            with patch.dict(os.environ, {}, clear=True):
                import importlib
                import src.adapters.openai_adapter as adapter_module
                importlib.reload(adapter_module)

                adapter = adapter_module.OpenAIAdapter(api_key="test-key")

                mock_OpenAI.assert_called_once_with(
                    api_key="test-key",
                    base_url=None,
                    http_client=None,
                )

    def test_with_custom_base_url(self):
        """Test adapter uses custom base URL."""
        import sys
        mock_openai_module = MagicMock()
        mock_OpenAI = MagicMock()
        mock_openai_module.OpenAI = mock_OpenAI
        with patch.dict(sys.modules, {"openai": mock_openai_module}):
            env = {"OPENAI_BASE_URL": "https://proxy.example.com/v1"}
            with patch.dict(os.environ, env, clear=True):
                import importlib
                import src.adapters.openai_adapter as adapter_module
                importlib.reload(adapter_module)

                adapter = adapter_module.OpenAIAdapter(api_key="test-key")

                call_kwargs = mock_OpenAI.call_args[1]
                assert call_kwargs["base_url"] == "https://proxy.example.com/v1"

    @patch("src.adapters.openai_adapter.httpx.Client")
    def test_with_custom_headers(self, mock_httpx_client):
        """Test adapter creates httpx client with custom headers."""
        import sys
        mock_openai_module = MagicMock()
        mock_OpenAI = MagicMock()
        mock_openai_module.OpenAI = mock_OpenAI
        with patch.dict(sys.modules, {"openai": mock_openai_module}):
            env = {"OPENAI_HEADER_X_Tenant_Id": "tenant-123"}
            with patch.dict(os.environ, env, clear=True):
                import importlib
                import src.adapters.openai_adapter as adapter_module
                importlib.reload(adapter_module)

                adapter = adapter_module.OpenAIAdapter(api_key="test-key")

                mock_httpx_client.assert_called_once()
                call_kwargs = mock_httpx_client.call_args[1]
                assert call_kwargs["headers"] == {"X-Tenant-Id": "tenant-123"}


class TestGeminiAdapterConfiguration:
    """Tests for GeminiAdapter initialization with custom configuration."""

    def test_default_initialization(self):
        """Test adapter initializes with defaults when no custom config."""
        import sys
        mock_genai = MagicMock()
        mock_types = MagicMock()
        mock_google = MagicMock()
        mock_google.genai = mock_genai
        mock_google.genai.types = mock_types
        with patch.dict(sys.modules, {
            "google": mock_google,
            "google.genai": mock_genai,
            "google.genai.types": mock_types,
        }):
            with patch.dict(os.environ, {}, clear=True):
                import importlib
                import src.adapters.gemini_adapter as adapter_module
                importlib.reload(adapter_module)

                adapter = adapter_module.GeminiAdapter(api_key="test-key")

                mock_genai.Client.assert_called_once_with(api_key="test-key")

    def test_with_custom_headers(self):
        """Test adapter uses http_options with custom headers."""
        import sys
        mock_genai = MagicMock()
        mock_types = MagicMock()
        mock_google = MagicMock()
        mock_google.genai = mock_genai
        mock_google.genai.types = mock_types
        with patch.dict(sys.modules, {
            "google": mock_google,
            "google.genai": mock_genai,
            "google.genai.types": mock_types,
        }):
            env = {"GEMINI_HEADER_X_Custom": "value"}
            with patch.dict(os.environ, env, clear=True):
                import importlib
                import src.adapters.gemini_adapter as adapter_module
                importlib.reload(adapter_module)

                adapter = adapter_module.GeminiAdapter(api_key="test-key")

                call_kwargs = mock_genai.Client.call_args[1]
                assert "http_options" in call_kwargs
                assert call_kwargs["http_options"]["headers"] == {"X-Custom": "value"}

    def test_base_url_logs_warning(self, caplog):
        """Test that setting GEMINI_BASE_URL logs a warning."""
        import sys
        import logging
        mock_genai = MagicMock()
        mock_types = MagicMock()
        mock_google = MagicMock()
        mock_google.genai = mock_genai
        mock_google.genai.types = mock_types
        with patch.dict(sys.modules, {
            "google": mock_google,
            "google.genai": mock_genai,
            "google.genai.types": mock_types,
        }):
            env = {"GEMINI_BASE_URL": "https://proxy.example.com"}
            with patch.dict(os.environ, env, clear=True):
                with caplog.at_level(logging.WARNING):
                    import importlib
                    import src.adapters.gemini_adapter as adapter_module
                    importlib.reload(adapter_module)

                    adapter = adapter_module.GeminiAdapter(api_key="test-key")

                    # Check warning was logged
                    assert any("GEMINI_BASE_URL" in record.message for record in caplog.records)


# Run with: pytest tests/test_adapters.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
