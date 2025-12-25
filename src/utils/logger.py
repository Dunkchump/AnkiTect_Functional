"""Logger utilities."""

import logging
from typing import Optional


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Setup a logger instance."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger
