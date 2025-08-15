"""
Utility functions for retry logic, progress tracking, and error recovery.
"""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from .logging import get_logger

T = TypeVar("T")
console = Console()


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    Decorator that implements retry logic with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        exceptions: Tuple of exceptions to catch and retry on
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            delay = base_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        # Final attempt failed, re-raise the exception
                        logger = get_logger()
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
                        raise

                    # Calculate delay for next attempt
                    delay = min(delay * exponential_base, max_delay)

                    logger = get_logger()
                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                    )
                    logger.info(f"Retrying in {delay:.1f} seconds...")

                    time.sleep(delay)

            # This should never be reached, but just in case
            raise last_exception

        return wrapper

    return decorator


def create_progress_bar(description: str, total: Optional[int] = None) -> Progress:
    """
    Create a rich progress bar with consistent styling.

    Args:
        description: Description of the operation
        total: Total number of items to process (None for indeterminate)

    Returns:
        Configured Progress instance
    """
    columns = [
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ]

    if total is not None:
        columns.append(TextColumn("({task.completed}/{task.total})"))

    columns.append(TimeElapsedColumn())

    return Progress(*columns, console=console, description=description)


def process_with_progress(
    items: list[Any],
    process_func: Callable[[Any], Any],
    description: str = "Processing",
    show_progress: bool = True,
) -> list[Any]:
    """
    Process a list of items with a progress bar.

    Args:
        items: List of items to process
        process_func: Function to apply to each item
        description: Description for the progress bar
        show_progress: Whether to show progress bar

    Returns:
        List of processed items
    """
    if not show_progress:
        return [process_func(item) for item in items]

    results = []
    with create_progress_bar(description, len(items)) as progress:
        task = progress.add_task(description, total=len(items))

        for item in items:
            try:
                result = process_func(item)
                results.append(result)
            except Exception as e:
                logger = get_logger()
                logger.error(f"Failed to process item: {e}")
                # Continue with other items
                continue
            finally:
                progress.advance(task)

    return results


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning a default value if denominator is zero.

    Args:
        numerator: The numerator
        denominator: The denominator
        default: Default value to return if division is not possible

    Returns:
        Result of division or default value
    """
    try:
        return numerator / denominator if denominator != 0 else default
    except (TypeError, ZeroDivisionError):
        return default


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def chunk_list(items: list[Any], chunk_size: int) -> list[list[Any]]:
    """
    Split a list into chunks of specified size.

    Args:
        items: List to chunk
        chunk_size: Size of each chunk

    Returns:
        List of chunks
    """
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def safe_filename(filename: str) -> str:
    """
    Convert a string to a safe filename by removing/replacing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Safe filename
    """
    import re

    # Remove or replace invalid characters
    safe = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # Remove leading/trailing spaces and dots
    safe = safe.strip(" .")
    # Limit length
    if len(safe) > 200:
        safe = safe[:200]
    return safe or "untitled"
