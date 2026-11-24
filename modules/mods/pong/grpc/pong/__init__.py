"""The pong mod's service surface (§7): contract + implementation.

The cog never touches the domain or its collections directly; it goes
through `mod_service("pong")` and the Protocol in `contract.py`.
"""

from botforge.mods.pong.grpc.contract import PongContract
from botforge.mods.pong.grpc.service import PongServiceImpl

__all__ = ["PongContract", "PongServiceImpl"]
