"""Logger utilities for AnkiTect.

Provides centralized logging with both console and optional file output.
Usage:
    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Processing started")
    logger.error("Something failed", exc_info=True)
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional


# Module-level cache of configured loggers
_configured = False


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
) -> None:
    """Configure the root AnkiTect logger.
    
    Call once at application startup. Subsequent calls are no-ops.
    
    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file (created if absent)
    """
    global _configured
    if _configured:
        return
    
    root_logger = logging.getLogger("ankitect")
    root_logger.setLevel(level)
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    root_logger.addHandler(console)
    
    # Optional file handler
    if log_file:
        try:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            ))
            root_logger.addHandler(file_handler)
        except OSError:
            root_logger.warning(f"Could not create log file: {log_file}")
    
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the ankitect namespace.
    
    Args:
        name: Module name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    # Auto-setup with defaults if not yet configured
    if not _configured:
        setup_logging()
    return logging.getLogger(f"ankitect.{name}")
