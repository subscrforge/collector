"""Logging configurations."""

import sys

from loguru import logger

FORMATTER = " ".join(
    [
        "<g>{time:YYYY-MM-DD HH:mm:ss.SSS}</g> ",
        "[<lvl>{level}</lvl>] ",
        "<c>{name}</c> : ",
        "{message}",
    ]
)

logger.remove()
logger.add(sys.stderr, format=FORMATTER, enqueue=True)

logger = logger.opt(colors=True)
