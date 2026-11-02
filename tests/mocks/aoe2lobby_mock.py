"""Aoe2LobbyMock: in-memory mocks for the aoe2lobby WS provider.

Three layers, one file (the discord_mock pattern):

- ``MockLobbyServer``: a real asyncio WebSocket server speaking the
  aoe2lobby wire protocol (subscribe/match_all/match_update/
  player_status frames) — the integration layer against which the
  REAL adapter runs, no network;
- ``MockAoe2LobbyAdapter``: the adapter's seam replaced wholesale —
  unit tests fold frames and assert the derived events without any
  socket;
- ``frame builders``: the payload fixtures (a lobby, a launched
  match, a settings change, a leave) typed as the REAL wire shape.

The wire contract (the 2026-11-02 live captures):

- the client sends: ``{"action": "subscribe", "type": "matches"|"players",
  "context": "lobby"|"spectate", "ids": [...]}``;
- the server pushes: ``{"lobby_match_all": {<matchid>: {...}}}``,
  ``{"lobby_match_update": {...}}``, ``{"spectate_match_all": ...}``,
  ``{"player_status": {<profileid>: {...}}}``;
- a match payload: matchid, description, map_name, mode, population,
  slots (s1..s8 -> status/color/team/civilization/profileid/name...),
  host_profileid, password, created_time...
- profile ids ride as INTs in the slots, STRs in the keys — the
  adapter casts (heterogeneous server-side types, reference §3).
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# the frame fixtures (the REAL wire shapes)
# ---------------------------------------------------------------------------


def lobby_match(
    match_id: int | str,
    profile_ids: list[int],
    *,
    map_name: str = "Arena",
    description: str = "test",
    password: bool = False,
    slots_taken: int | None = None,
) -> dict[str, Any]:
    """Build one lobby_match payload (the lobby_match_all entry shape)."""
    slots: dict[str, Any] = {}
    for index in range(8):
        slot_key = f"s{index + 1}"
        if index < len(profile_ids):
            slots[slot_key] = {
                "status": 3,
                "color": index + 1,
                "team": 1,
                "civilization": 2,
                "profileid": int(profile_ids[index]),
                "name": f"Player{index + 1}",
                "country": "fr",
            }
        else:
            slots[slot_key] = {
                "status": 0,
                "color": None,
                "team": None,
                "civilization": None,
                "profileid": None,
            }
    return {
        "matchid": int(match_id),
        "description": description,
        "map_name": map_name,
        "mapid": 25,
        "mode": 0,
        "password": password,
        "population": 200,
        "created_time": 1793618445,
        "host_profileid": int(profile_ids[0]) if profile_ids else None,
        "slots": slots,
        "slots_taken": slots_taken if slots_taken is not None else len(profile_ids),
        "slots_total": 8,
        "game": 2,
        "ai_difficulty": 5,
        "cheats": False,
        "lock_teams": True,
        "record": True,
        "reveal_map": 0,
        "shared_exploration": True,
        "size": 2,
    }


def player_status(
    profile_id: int | str, status: int | None, match_id: int | None = None
) -> dict[str, Any]:
    """Build one player_status frame body (the status push shape)."""
    return {
        str(profile_id): {
            "status": status,
            "matchid": match_id,
            "steam_lobbyid": None,
        }
    }


# ---------------------------------------------------------------------------
# MockLobbyServer: the wire-level mock (integration tests)
# ---------------------------------------------------------------------------


class MockLobbyServer:
    """A real asyncio WS server speaking the aoe2lobby protocol.

    The REAL adapter connects (point its ws_url here), subscribes, and
    the test drives the world: push_match_all, push_match_update,
    push_player_status, drop_match — the frames the real aoe2lobby
    sends, replayable deterministically.
    """

    def __init__(self) -> None:
        self._server: Any = None
        self._clients: list[Any] = []
        self._subscriptions: list[dict[str, Any]] = []
        self._matches: dict[str, dict[str, Any]] = {}
        self.port = 0

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/ws/"

    async def start(self) -> str:
        """Serve on an ephemeral port; return the ws url."""
        import websockets

        self._server = await websockets.serve(self._ws_session, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self.url

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _ws_session(self, ws: Any, _path: str = "") -> None:
        self._clients.append(ws)
        try:
            async for raw in ws:
                message = json.loads(raw)
                if message.get("action") == "subscribe":
                    self._subscriptions.append(message)
                    # the initial snapshot (the real server's shape)
                    await self._send(ws, {"lobby_match_all": dict(self._matches)})
                    await self._send(ws, {"spectate_match_all": {}})
        finally:
            if ws in self._clients:
                self._clients.remove(ws)

    async def _send(self, ws: Any, frame: dict[str, Any]) -> None:
        await ws.send(json.dumps(frame))

    async def broadcast(self, frame: dict[str, Any]) -> None:
        """Push one frame to every connected client (the server's push)."""
        for ws in list(self._clients):
            await self._send(ws, frame)

    # the world-driving API --------------------------------------------

    async def push_match_all(self, matches: dict[str, dict[str, Any]]) -> None:
        """Replace the lobby world (the periodic tick's snapshot)."""
        self._matches = dict(matches)
        await self.broadcast({"lobby_match_all": dict(matches)})

    async def push_match_update(self, match_id: str, match: dict[str, Any]) -> None:
        """Push one match's live change (civ/map/settings)."""
        self._matches[match_id] = match
        await self.broadcast({"lobby_match_update": {match_id: match}})

    async def drop_match(self, match_id: str) -> None:
        """Drop one match (the lobby closed)."""
        self._matches.pop(match_id, None)
        await self.broadcast({"lobby_match_all": dict(self._matches)})

    async def push_player_status(self, body: dict[str, Any]) -> None:
        """Push the players channel's status update."""
        await self.broadcast({"player_status": body})


__all__ = ["MockLobbyServer", "lobby_match", "player_status"]
