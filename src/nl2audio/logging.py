"""
Logging configuration and utilities for nl2audio.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Custom theme for better log formatting
THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red",
        "critical": "red bold",
        "success": "green",
    }
)

console = Console(theme=THEME)


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        # Add color to the level name
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logging(
    log_file: Optional[Path] = None, level: str = "INFO", enable_rich: bool = True
) -> logging.Logger:
    """
    Set up logging configuration.

    Args:
        log_file: Optional path to log file
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_rich: Whether to use Rich formatting for console output

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("nl2audio")
    logger.setLevel(getattr(logging, level.upper()))

    # Clear any existing handlers
    logger.handlers.clear()

    # Console handler with Rich formatting
    if enable_rich:
        console_handler = RichHandler(
            console=console, show_time=True, show_path=False, markup=True
        )
        console_handler.setLevel(getattr(logging, level.upper()))
        logger.addHandler(console_handler)
    else:
        # Fallback to colored console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        formatter = ColoredFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler if log_file is specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # File gets all logs

        # Simple formatter for file output
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (defaults to 'nl2audio')

    Returns:
        Logger instance
    """
    return logging.getLogger(name or "nl2audio")


# Convenience functions for common logging patterns
def log_success(message: str) -> None:
    """Log a success message."""
    logger = get_logger()
    logger.info(f"✅ {message}")


def log_warning(message: str) -> None:
    """Log a warning message."""
    logger = get_logger()
    logger.warning(f"⚠️  {message}")


def log_error(message: str, exc_info: Optional[Exception] = None) -> None:
    """Log an error message."""
    logger = get_logger()
    if exc_info:
        logger.error(f"❌ {message}", exc_info=exc_info)
    else:
        logger.error(f"❌ {message}")


def log_debug(message: str) -> None:
    """Log a debug message."""
    logger = get_logger()
    logger.debug(f"🔍 {message}")


def log_info(message: str) -> None:
    """Log an info message."""
    logger = get_logger()
    logger.info(f"ℹ️  {message}")
