"""
core/logger.py
Centralised logging setup for LocalClaw.
"""

import logging
import sys
from core.config import Config


def get_logger(name: str, cfg: Config = None) -> logging.Logger:
    """
    Return a logger with the given name.
    On first call, sets up file + stream handlers based on cfg.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger   # already configured

    level = getattr(logging, (cfg.LOG_LEVEL if cfg else "INFO").upper(), logging.INFO)
    logger.setLevel(level)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")

    # Stream handler (stdout)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # File handler
    log_file = cfg.LOG_FILE if cfg else "localclaw.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
