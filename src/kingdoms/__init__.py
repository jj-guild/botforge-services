"""Kingdoms Discord bot platform: generic core, Discord implementation, mods and configs."""

import os

__version__ = os.environ.get("KINGDOMS_VERSION", "").strip() or "0.1.0"
