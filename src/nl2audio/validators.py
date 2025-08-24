"""
Comprehensive validation and health check utilities for nl2audio.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Literal, Optional
from urllib.parse import urlparse

from .config import AppConfig


@dataclass
class CheckResult:
    """Result of a health check."""

    name: str
    status: Literal["pass", "warn", "fail"]
    message: str
    remediation: Optional[str] = None


def check_output_dir(cfg: AppConfig) -> CheckResult:
    """Check that output directory exists and is writable."""
    try:
        # Ensure directory exists
        cfg.output_dir.mkdir(parents=True, exist_ok=True)

        # Test write permissions
        test_file = cfg.output_dir / ".test_write"
        test_file.write_text("test")
        test_file.unlink()

        # Test creating episodes subdirectory
        episodes_dir = cfg.output_dir / "episodes"
        episodes_dir.mkdir(exist_ok=True)

        # Test creating a test file in episodes directory
        test_episode = episodes_dir / ".test_episode"
        test_episode.write_text("test")
        test_episode.unlink()

        return CheckResult(
            name="Output Directory",
            status="pass",
            message=f"Output directory '{cfg.output_dir}' is accessible and writable",
            remediation=None,
        )

    except PermissionError:
        return CheckResult(
            name="Output Directory",
            status="fail",
            message=f"Cannot write to output directory: {cfg.output_dir}",
            remediation="Check directory permissions or choose a different location",
        )
    except Exception as e:
        return CheckResult(
            name="Output Directory",
            status="fail",
            message=f"Output directory error: {e}",
            remediation="Verify the path is valid and accessible",
        )


def check_ffmpeg() -> CheckResult:
    """Check that FFmpeg is available in PATH."""
    try:
        # Check if ffmpeg is in PATH
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            return CheckResult(
                name="FFmpeg",
                status="fail",
                message="FFmpeg not found in PATH",
                remediation="Install FFmpeg and ensure it's in your system PATH",
            )

        # Test if ffmpeg is callable
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            return CheckResult(
                name="FFmpeg",
                status="pass",
                message="FFmpeg is available and working",
                remediation=None,
            )
        else:
            return CheckResult(
                name="FFmpeg",
                status="fail",
                message="FFmpeg found but failed to execute",
                remediation="Reinstall FFmpeg or check system permissions",
            )

    except subprocess.TimeoutExpired:
        return CheckResult(
            name="FFmpeg",
            status="warn",
            message="FFmpeg test timed out",
            remediation="FFmpeg may be slow to start - this is usually not a problem",
        )
    except Exception as e:
        return CheckResult(
            name="FFmpeg",
            status="fail",
            message=f"FFmpeg check failed: {e}",
            remediation="Verify FFmpeg installation and PATH configuration",
        )


def check_openai_key() -> CheckResult:
    """Check that OpenAI API key is present and valid format."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return CheckResult(
            name="OpenAI API Key",
            status="fail",
            message="OPENAI_API_KEY environment variable is not set",
            remediation="Set OPENAI_API_KEY in your environment or .env file",
        )

    if not api_key.startswith("sk-"):
        return CheckResult(
            name="OpenAI API Key",
            status="fail",
            message="OPENAI_API_KEY appears to be invalid (should start with 'sk-')",
            remediation="Verify your OpenAI API key format",
        )

    return CheckResult(
        name="OpenAI API Key",
        status="pass",
        message="OpenAI API key is present and appears valid",
        remediation=None,
    )


def check_openai_probe() -> CheckResult:
    """Probe OpenAI API to verify connectivity and key validity."""
    try:
        import openai

        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Quick test to list models (lightweight operation)
        models = client.models.list()

        if models.data:
            return CheckResult(
                name="OpenAI API Connectivity",
                status="pass",
                message="Successfully connected to OpenAI API",
                remediation=None,
            )
        else:
            return CheckResult(
                name="OpenAI API Connectivity",
                status="warn",
                message="Connected to OpenAI API but no models returned",
                remediation="Check your OpenAI account status and billing",
            )

    except ImportError:
        return CheckResult(
            name="OpenAI API Connectivity",
            status="fail",
            message="OpenAI Python client not available",
            remediation="Install openai package: pip install openai",
        )
    except Exception as e:
        error_msg = str(e)
        if "authentication" in error_msg.lower() or "invalid" in error_msg.lower():
            return CheckResult(
                name="OpenAI API Connectivity",
                status="fail",
                message="OpenAI API key is invalid or expired",
                remediation="Verify your API key and check your OpenAI account",
            )
        elif "rate limit" in error_msg.lower():
            return CheckResult(
                name="OpenAI API Connectivity",
                status="warn",
                message="OpenAI API rate limit reached",
                remediation="Wait a moment and try again, or check your usage limits",
            )
        else:
            return CheckResult(
                name="OpenAI API Connectivity",
                status="fail",
                message=f"OpenAI API connection failed: {e}",
                remediation="Check your internet connection and OpenAI service status",
            )


def check_gmail_login(cfg: AppConfig) -> CheckResult:
    """Check Gmail connectivity based on configured method."""
    if not cfg.gmail.enabled:
        return CheckResult(
            name="Gmail", status="pass", message="Gmail is disabled", remediation=None
        )

    if not cfg.gmail.user:
        return CheckResult(
            name="Gmail",
            status="fail",
            message="Gmail user is not configured",
            remediation="Set gmail.user in your configuration",
        )

    if cfg.gmail.method == "oauth":
        return check_gmail_oauth(cfg)
    else:
        return check_gmail_imap(cfg)


def check_gmail_oauth(cfg: AppConfig) -> CheckResult:
    """Check Gmail OAuth connectivity."""
    try:
        from .gmail_oauth import (
            build_gmail_service,
            get_label_id,
            get_stored_credentials,
        )

        # Check if we have stored credentials
        creds = get_stored_credentials(cfg.gmail.user)
        if not creds:
            return CheckResult(
                name="Gmail OAuth",
                status="fail",
                message=f"No OAuth credentials found for {cfg.gmail.user}",
                remediation="Run 'nl2audio connect-gmail' to authenticate",
            )

        # Test the credentials by building a service and making a simple API call
        service = build_gmail_service(creds)

        # Try to get user profile (lightweight operation)
        profile = service.users().getProfile(userId="me").execute()
        if profile.get("emailAddress") != cfg.gmail.user:
            return CheckResult(
                name="Gmail OAuth",
                status="warn",
                message=f"OAuth credentials valid but email mismatch: {profile.get('emailAddress')} vs {cfg.gmail.user}",
                remediation="Re-authenticate with 'nl2audio connect-gmail'",
            )

        # Check if the configured label exists
        label_id = get_label_id(service, cfg.gmail.label)
        if not label_id:
            return CheckResult(
                name="Gmail OAuth",
                status="warn",
                message=f"OAuth working but label '{cfg.gmail.label}' not found",
                remediation="Check label name or create the label in Gmail",
            )

        return CheckResult(
            name="Gmail OAuth",
            status="pass",
            message=f"OAuth working for {cfg.gmail.user}, label '{cfg.gmail.label}' found",
            remediation=None,
        )

    except ImportError:
        return CheckResult(
            name="Gmail OAuth",
            status="fail",
            message="Gmail OAuth dependencies not available",
            remediation="Install required packages: pip install google-auth-oauthlib google-api-python-client keyring",
        )
    except Exception as e:
        return CheckResult(
            name="Gmail OAuth",
            status="fail",
            message=f"OAuth check failed: {e}",
            remediation="Run 'nl2audio connect-gmail' to re-authenticate",
        )


def check_gmail_imap(cfg: AppConfig) -> CheckResult:
    """Check Gmail IMAP connectivity."""
    if not cfg.gmail.app_password:
        return CheckResult(
            name="Gmail IMAP",
            status="fail",
            message="Gmail app password is not configured",
            remediation="Set gmail.app_password in your configuration or use OAuth",
        )

    try:
        import imaplib
        import socket

        # Test IMAP connection with timeout
        mailbox = imaplib.IMAP4_SSL("imap.gmail.com", timeout=10)

        try:
            # Try to login
            mailbox.login(cfg.gmail.user, cfg.gmail.app_password)

            # Try to select a folder (lightweight operation)
            mailbox.select("INBOX")

            # Close connection
            mailbox.close()
            mailbox.logout()

            return CheckResult(
                name="Gmail IMAP",
                status="pass",
                message=f"IMAP working for {cfg.gmail.user}",
                remediation=None,
            )

        except imaplib.IMAP4.error as e:
            error_msg = str(e).lower()
            if (
                "invalid credentials" in error_msg
                or "authentication failed" in error_msg
            ):
                return CheckResult(
                    name="Gmail IMAP",
                    status="fail",
                    message="Invalid Gmail credentials",
                    remediation="Check your username and app password, or use OAuth instead",
                )
            else:
                return CheckResult(
                    name="Gmail IMAP",
                    status="fail",
                    message=f"IMAP authentication error: {e}",
                    remediation="Verify Gmail settings and app password",
                )

    except socket.timeout:
        return CheckResult(
            name="Gmail IMAP",
            status="warn",
            message="IMAP connection timed out",
            remediation="Check your internet connection and Gmail server status",
        )
    except Exception as e:
        return CheckResult(
            name="Gmail IMAP",
            status="fail",
            message=f"IMAP check failed: {e}",
            remediation="Check network connectivity and Gmail settings",
        )


def check_rss_feeds(cfg: AppConfig) -> CheckResult:
    """Validate RSS feed URLs if RSS is enabled."""
    if not cfg.rss.enabled:
        return CheckResult(
            name="RSS Feeds",
            status="pass",
            message="RSS is disabled in configuration",
            remediation=None,
        )

    if not cfg.rss.feeds:
        return CheckResult(
            name="RSS Feeds",
            status="fail",
            message="RSS is enabled but no feeds are configured",
            remediation="Add RSS feed URLs to your configuration",
        )

    invalid_urls = []
    for feed_url in cfg.rss.feeds:
        try:
            parsed = urlparse(feed_url)
            if not parsed.scheme or not parsed.netloc:
                invalid_urls.append(feed_url)
        except Exception:
            invalid_urls.append(feed_url)

    if invalid_urls:
        return CheckResult(
            name="RSS Feeds",
            status="fail",
            message=f"Invalid RSS feed URLs: {', '.join(invalid_urls)}",
            remediation="Fix the invalid URLs in your RSS configuration",
        )

    return CheckResult(
        name="RSS Feeds",
        status="pass",
        message=f"RSS feeds configured with {len(cfg.rss.feeds)} valid URLs",
        remediation=None,
    )


def validate_config(cfg: AppConfig) -> List[CheckResult]:
    """Validate configuration without external API calls."""
    results = []

    # Basic configuration checks
    results.append(check_output_dir(cfg))
    results.append(check_ffmpeg())
    results.append(check_openai_key())
    results.append(check_gmail_login(cfg))
    results.append(check_rss_feeds(cfg))

    return results


def validate_runtime(
    cfg: AppConfig, *, check_openai: bool = False, check_gmail: bool = False
) -> List[CheckResult]:
    """Validate runtime environment with optional external checks."""
    results = validate_config(cfg)

    # Optional external checks
    if check_openai:
        results.append(check_openai_probe())

    if check_gmail and cfg.gmail.enabled:
        # Gmail connectivity is already checked in validate_config
        # This could be extended with additional runtime checks if needed
        pass

    return results


def get_check_summary(results: List[CheckResult]) -> dict:
    """Get summary statistics of check results."""
    total = len(results)
    passed = len([r for r in results if r.status == "pass"])
    warnings = len([r for r in results if r.status == "warn"])
    failed = len([r for r in results if r.status == "fail"])

    return {
        "total": total,
        "passed": passed,
        "warnings": warnings,
        "failed": failed,
        "all_passed": failed == 0,
        "has_warnings": warnings > 0,
    }


def validate_prep_config(cfg: AppConfig) -> List[CheckResult]:
    """Validate prep configuration settings."""
    results = []

    valid_models = ["gpt-3.5-turbo", "gpt-4o"]
    if cfg.prep.model not in valid_models:
        results.append(
            CheckResult(
                name="Prep Model",
                status="fail",
                message=f"Invalid model '{cfg.prep.model}'. Must be one of: {', '.join(valid_models)}",
                remediation="Set a valid prep model in your configuration",
            )
        )
    else:
        results.append(
            CheckResult(
                name="Prep Model",
                status="pass",
                message=f"Prep model configured: {cfg.prep.model}",
                remediation=None,
            )
        )

    if not 0.0 <= cfg.prep.temperature <= 2.0:
        results.append(
            CheckResult(
                name="Prep Temperature",
                status="fail",
                message=f"Temperature must be between 0.0 and 2.0, got: {cfg.prep.temperature}",
                remediation="Set temperature to a value between 0.0 and 2.0",
            )
        )
    else:
        results.append(
            CheckResult(
                name="Prep Temperature",
                status="pass",
                message=f"Temperature configured: {cfg.prep.temperature}",
                remediation=None,
            )
        )

    if not 100 <= cfg.prep.max_tokens <= 4000:
        results.append(
            CheckResult(
                name="Prep Max Tokens",
                status="fail",
                message=f"Max tokens must be between 100 and 4000, got: {cfg.prep.max_tokens}",
                remediation="Set max tokens to a value between 100 and 4000",
            )
        )
    else:
        results.append(
            CheckResult(
                name="Prep Max Tokens",
                status="pass",
                message=f"Max tokens configured: {cfg.prep.max_tokens}",
                remediation=None,
            )
        )

    if cfg.prep.enabled:
        results.append(
            CheckResult(
                name="Prep Status",
                status="pass",
                message="Prep LLM is enabled and ready to use",
                remediation=None,
            )
        )
    else:
        results.append(
            CheckResult(
                name="Prep Status",
                status="warn",
                message="Prep LLM is disabled (use --prep flag or enable in config)",
                remediation="Enable prep in config or use --prep flag when running commands",
            )
        )

    return results
