"""BotForge Discord bot platform: generic core, Discord implementation, mods and configs."""

import os

__version__ = os.environ.get("BOTFORGE_VERSION", "").strip() or "0.1.0"
