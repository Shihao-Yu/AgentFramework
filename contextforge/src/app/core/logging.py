"""
Colorful logging configuration using rich.
"""

import logging
import os

from rich.console import Console
from rich.logging import RichHandler

console = Console()


def setup_logging(level: str | None = None) -> None:
    """
    Configure colorful logging with rich.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). 
               Defaults to DEBUG if DEBUG=true in env, else INFO.
    """
    if level is None:
        debug_mode = os.environ.get("DEBUG", "false").lower() == "true"
        level = "DEBUG" if debug_mode else "INFO"
    
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                tracebacks_show_locals=False,
                show_path=False,
                markup=True,
            )
        ],
        force=True,
    )
    
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
