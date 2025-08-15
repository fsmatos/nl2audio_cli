"""
Validation and health check utilities for nl2audio.
"""

from __future__ import annotations

import os
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


def check_environment() -> None:
    """Check that required environment variables are set."""
    missing_vars = []

    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        missing_vars.append("OPENAI_API_KEY")

    if missing_vars:
        error_text = Text()
        error_text.append("❌ Missing required environment variables:\n\n", style="red")
        for var in missing_vars:
            error_text.append(f"  • {var}\n", style="yellow")
        error_text.append(
            "\nPlease set these variables in your environment or .env file.",
            style="white",
        )

        console.print(
            Panel(error_text, title="Environment Validation Failed", border_style="red")
        )
        raise ValidationError(
            f"Missing environment variables: {', '.join(missing_vars)}"
        )


def check_openai_api_key() -> str:
    """Validate OpenAI API key and return it if valid."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValidationError("OPENAI_API_KEY environment variable is not set")

    if not api_key.startswith("sk-"):
        raise ValidationError(
            "OPENAI_API_KEY appears to be invalid (should start with 'sk-')"
        )

    return api_key


def check_output_directory(output_dir: Path) -> None:
    """Check that output directory is accessible and writable."""
    try:
        # Ensure directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Test write permissions
        test_file = output_dir / ".test_write"
        test_file.write_text("test")
        test_file.unlink()

    except PermissionError:
        raise ValidationError(f"Cannot write to output directory: {output_dir}")
    except Exception as e:
        raise ValidationError(f"Output directory error: {e}")


def check_gmail_credentials(user: str, app_password: str) -> None:
    """Validate Gmail credentials format."""
    if not user or not user.strip():
        raise ValidationError("Gmail user email is required")

    if not app_password or not app_password.strip():
        raise ValidationError("Gmail app password is required")

    if "@" not in user:
        raise ValidationError("Gmail user should be a valid email address")

    # Gmail app passwords can vary in length, just ensure it's not empty
    if len(app_password.strip()) < 8:
        raise ValidationError("Gmail app password appears to be too short")


def validate_config_health() -> None:
    """Run all validation checks."""
    console.print("🔍 Running configuration health checks...")

    try:
        # Check environment
        check_environment()
        console.print("✅ Environment variables validated")

        # Check OpenAI API key
        api_key = check_openai_api_key()
        console.print("✅ OpenAI API key validated")

        console.print("✅ All validation checks passed!")

    except ValidationError as e:
        console.print(f"❌ Configuration validation failed: {e}")
        raise
    except Exception as e:
        console.print(f"❌ Unexpected validation error: {e}")
        raise
