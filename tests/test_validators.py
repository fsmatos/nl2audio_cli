"""
Tests for nl2audio validators module.
"""

import os
from pathlib import Path

from nl2audio.config import AppConfig, GmailConfig
from nl2audio.validators import (
    check_ffmpeg,
    check_gmail_imap,
    check_gmail_oauth,
    check_openai_key,
    check_output_dir,
    get_check_summary,
    validate_config,
    validate_runtime,
)


class TestOutputDirectory:
    """Test output directory validation."""

    def test_output_dir_success(self, temp_dir):
        """Test successful output directory validation."""
        config = AppConfig(output_dir=temp_dir)
        result = check_output_dir(config)

        assert result.status == "pass"
        assert "accessible and writable" in result.message
        assert result.remediation is None

    def test_output_dir_permission_error(self, temp_dir):
        """Test output directory permission error."""
        # Make directory read-only
        os.chmod(temp_dir, 0o444)

        config = AppConfig(output_dir=temp_dir)
        result = check_output_dir(config)

        assert result.status == "fail"
        assert "Cannot write to output directory" in result.message
        assert "Check directory permissions" in result.remediation

        # Restore permissions
        os.chmod(temp_dir, 0o755)

    def test_output_dir_invalid_path(self):
        """Test output directory with invalid path."""
        config = AppConfig(output_dir=Path("/invalid/path/that/does/not/exist"))
        result = check_output_dir(config)

        assert result.status == "fail"
        assert "Output directory error" in result.message


class TestFFmpeg:
    """Test FFmpeg validation."""

    def test_ffmpeg_mock_success(self, mock_ffmpeg):
        """Test FFmpeg check with mocked availability."""
        result = check_ffmpeg()

        assert result.status == "pass"
        assert "FFmpeg is available and working" in result.message
        assert result.remediation is None

    def test_ffmpeg_not_found(self, monkeypatch):
        """Test FFmpeg check when not found."""

        def mock_which(cmd):
            return None

        monkeypatch.setattr("shutil.which", mock_which)

        result = check_ffmpeg()

        assert result.status == "fail"
        assert "FFmpeg not found in PATH" in result.message
        assert "Install FFmpeg" in result.remediation


class TestOpenAI:
    """Test OpenAI validation."""

    def test_openai_key_success(self, mock_env_vars):
        """Test OpenAI API key validation."""
        result = check_openai_key()

        assert result.status == "pass"
        assert "OpenAI API key is valid" in result.message
        assert result.remediation is None

    def test_openai_key_missing(self, monkeypatch):
        """Test OpenAI API key when missing."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        result = check_openai_key()

        assert result.status == "fail"
        assert "OpenAI API key not found" in result.message
        assert "Set OPENAI_API_KEY" in result.remediation

    def test_openai_key_invalid_format(self, monkeypatch):
        """Test OpenAI API key with invalid format."""
        monkeypatch.setenv("OPENAI_API_KEY", "invalid-key-format")

        result = check_openai_key()

        assert result.status == "fail"
        assert "OpenAI API key format is invalid" in result.message
        assert "should start with 'sk-'" in result.remediation


class TestGmail:
    """Test Gmail validation."""

    def test_gmail_oauth_success(self, mock_gmail_service, mock_keyring):
        """Test Gmail OAuth validation success."""
        config = AppConfig(
            gmail=GmailConfig(enabled=True, user="test@gmail.com", method="oauth")
        )

        result = check_gmail_oauth(config)

        assert result.status == "pass"
        assert "Gmail OAuth is working" in result.message

    def test_gmail_oauth_no_credentials(self, mock_gmail_service, mock_keyring):
        """Test Gmail OAuth when no credentials stored."""
        config = AppConfig(
            gmail=GmailConfig(enabled=True, user="test@gmail.com", method="oauth")
        )

        result = check_gmail_oauth(config)

        assert result.status == "fail"
        assert "No OAuth credentials found" in result.message
        assert "run 'nl2audio connect-gmail'" in result.remediation

    def test_gmail_imap_success(self, monkeypatch):
        """Test Gmail IMAP validation success."""

        def mock_imaplib_connect(*args, **kwargs):
            class MockConnection:
                def login(self, user, password):
                    return ("OK", [b"Logged in"])

                def close(self):
                    pass

            return MockConnection()

        monkeypatch.setattr("imaplib.IMAP4_SSL", mock_imaplib_connect)

        config = AppConfig(
            gmail=GmailConfig(
                enabled=True,
                user="test@gmail.com",
                app_password="test_password",
                method="app_password",
            )
        )

        result = check_gmail_imap(config)

        assert result.status == "pass"
        assert "Gmail IMAP is working" in result.message


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_config_success(self, sample_config):
        """Test successful configuration validation."""
        results = validate_config(sample_config)

        # All checks should pass
        assert all(result.status == "pass" for result in results)
        assert len(results) > 0

    def test_validate_runtime_success(self, sample_config, mock_ffmpeg, mock_env_vars):
        """Test successful runtime validation."""
        results = validate_runtime(sample_config)

        # All checks should pass
        assert all(result.status == "pass" for result in results)
        assert len(results) > 0

    def test_validate_runtime_with_openai_probe(
        self, sample_config, mock_ffmpeg, mock_env_vars, mock_openai_client
    ):
        """Test runtime validation with OpenAI probing."""
        results = validate_runtime(sample_config, check_openai=True)

        # Should include OpenAI probe results
        openai_results = [r for r in results if "OpenAI" in r.name]
        assert len(openai_results) > 0
        assert all(r.status == "pass" for r in openai_results)


class TestCheckSummary:
    """Test check summary generation."""

    def test_get_check_summary(self, sample_config, mock_ffmpeg, mock_env_vars):
        """Test check summary generation."""
        results = validate_runtime(sample_config)
        summary = get_check_summary(results)

        assert "total" in summary
        assert "passed" in summary
        assert "warnings" in summary
        assert "failed" in summary

        # All should be numeric
        assert isinstance(summary["total"], int)
        assert isinstance(summary["passed"], int)
        assert isinstance(summary["warnings"], int)
        assert isinstance(summary["failed"], int)

        # Total should equal sum of individual counts
        assert (
            summary["total"]
            == summary["passed"] + summary["warnings"] + summary["failed"]
        )
