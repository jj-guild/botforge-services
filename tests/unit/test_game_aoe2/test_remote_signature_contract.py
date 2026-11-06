"""The remote's signatures ARE the real service's signatures — every method.

The 2026-11-06 pool round: the remote's update_map_pool/create_map_pool
took **kwargs while every Discord caller passes positionals — 'takes 1
positional argument' in production. The tests stayed green because the
flow tests use a FAKE service and the remote tests call with kwargs:
the pieces were tested, the SEAM never was.

This contract compares the remote's public API against the REAL
service's, method by method: any drift — a kwarg-only remote behind a
positional caller, a renamed parameter, a missing method — fails HERE,
at commit time.
"""

from __future__ import annotations

import inspect


def _public_methods(cls: type) -> dict[str, inspect.Signature]:
    return {
        name: inspect.signature(func)
        for name, func in vars(cls).items()
        if not name.startswith("_") and inspect.isfunction(func)
    }


def test_the_remote_mirrors_the_real_service_signatures() -> None:
    """Every public method of the remote matches the real service's shape."""
    from kingdoms.core.services.game_data import GameDataService
    from kingdoms.game_aoe2.remote_catalog import RemoteGameDataService

    real = _public_methods(GameDataService)
    remote = _public_methods(RemoteGameDataService)

    # the pool lifecycle is the Discord layer's daily bread — every
    # stage must exist on the remote
    lifecycle = (
        "create_map_pool",
        "update_map_pool",
        "transition_map_pool",
        "archive_map_pool",
        "hard_delete_map_pool",
        "get_map_pool",
        "list_map_pools",
    )
    missing = sorted(set(lifecycle) - set(remote))
    assert not missing, f"the remote lacks the pool lifecycle: {missing}"

    for name, real_sig in real.items():
        if name not in remote:
            continue  # the remote is a purposeful subset; what it EXPOSES must match
        remote_sig = remote[name]
        real_params = list(real_sig.parameters.values())[1:]  # drop self
        remote_params = list(remote_sig.parameters.values())[1:]
        real_shape = [(p.name, p.kind) for p in real_params]
        remote_shape = [(p.name, p.kind) for p in remote_params]
        assert real_shape == remote_shape, (
            f"{name}: the remote's signature drifted from the real service — "
            f"real {real_shape} vs remote {remote_shape}. The Discord callers "
            "pass positionals; a kwarg-only remote crashes in production."
        )
