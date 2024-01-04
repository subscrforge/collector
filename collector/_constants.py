"""Constants used by the module."""

import os
import sys
from pathlib import Path


def _get_default_cache_dir() -> Path:
    match sys.platform:
        case "win32":
            return Path(os.environ["TEMP"])
        case "darwin":
            return Path(os.environ["HOME"]) / "Library" / "Caches"
        case "linux":
            if env := os.getenv("XDG_CACHE_HOME"):
                return Path(env)
            return Path(os.environ["HOME"]) / ".cache"
        case _:
            raise NotImplementedError(f"Unsupported platform: {sys.platform}")


CACHE_DIR = _get_default_cache_dir() / "subscrforge" / "collector"
"""The path to the cache directory.

The cache directory is platform dependent, and is located at:

- Windows: `%TEMP%/subscrforge/collector`
- macOS: `$HOME/Library/Caches/subscrforge/collector`
- Linux: `$XDG_CACHE_HOME/subscrforge/collector` or `$HOME/.cache/subscrforge/collector`

Any other platform will be treated as unsupported, and will raise a
`NotImplementedError`.
"""
