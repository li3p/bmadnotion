"""bmadnotion - Sync BMAD project artifacts to Notion."""

__version__ = "0.1.0"

from bmadnotion.config import (
    Config,
    ConfigNotFoundError,
    TokenNotFoundError,
    load_config,
)

__all__ = [
    "__version__",
    "Config",
    "ConfigNotFoundError",
    "TokenNotFoundError",
    "load_config",
]
