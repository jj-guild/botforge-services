"""Status seam — server side and client helpers (kingdoms.v1.Status).

The bootstrap seam of the process split: lets any process assert
svc-core wiring (version, reachability) without domain dependencies.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import grpc

from kingdoms.rpc_generated.kingdoms.v1 import status_pb2, status_pb2_grpc


@dataclass(frozen=True, slots=True)
class CoreStatus:
    """Platform-agnostic status payload (pydantic-style plain model)."""

    version: str
    process: str


class _StatusServicer(status_pb2_grpc.StatusServicer):
    def __init__(self, status_provider: Callable[[], CoreStatus]) -> None:
        self._provider = status_provider

    async def GetCoreStatus(
        self,
        request: status_pb2.CoreStatusRequest,
        context: grpc.aio.ServicerContext,
    ) -> status_pb2.CoreStatus:
        """Serve the provider's current status payload as the wire message."""
        status = self._provider()
        return status_pb2.CoreStatus(version=status.version, process=status.process)


def build_status_server(
    status_provider: Callable[[], CoreStatus],
) -> grpc.aio.Server:
    """Build the aio gRPC server with the Status service bound."""
    server = grpc.aio.server()
    status_pb2_grpc.add_StatusServicer_to_server(_StatusServicer(status_provider), server)
    return server


async def fetch_core_status(core_uri: str) -> CoreStatus:
    """Fetch svc-core status over the wire (used by tests and preflight)."""
    async with grpc.aio.insecure_channel(core_uri) as channel:
        stub = status_pb2_grpc.StatusStub(channel)
        reply = await stub.GetCoreStatus(status_pb2.CoreStatusRequest(), timeout=5.0)
        return CoreStatus(version=reply.version, process=reply.process)


class _StatusServicerUpstream(_StatusServicer):
    """The Status servicer extended with the process's upstream stats.

    ``build_status_server`` stays the single binding point: a process
    that records its upstream calls passes a ``stats_provider`` and its
    stats ride the same port as its identity.
    """

    def __init__(
        self,
        status_provider: Callable[[], CoreStatus],
        stats_provider: Callable[[], Any] | None = None,
    ) -> None:
        super().__init__(status_provider)
        self._stats_provider = stats_provider

    async def GetUpstreamStats(
        self,
        request: status_pb2.UpstreamStatsRequest,
        context: grpc.aio.ServicerContext,
    ) -> status_pb2.UpstreamStatsReply:
        """Serve the process's upstream call statistics.

        The stats_provider may be sync or async (an aggregator that
        fetches its providers' own stats on demand).
        """
        import inspect

        entries = self._stats_provider() if self._stats_provider else []
        if inspect.isawaitable(entries):
            entries = await entries
        return status_pb2.UpstreamStatsReply(
            entries=[
                status_pb2.UpstreamStatEntry(
                    provider_id=str(e.get("provider_id", "")),
                    upstream=str(e.get("upstream", "")),
                    ok=bool(e.get("ok", False)),
                    never_called=bool(e.get("never_called", False)),
                    total_calls=int(e.get("total_calls", 0)),
                    total_errors=int(e.get("total_errors", 0)),
                    consecutive_failures=int(e.get("consecutive_failures", 0)),
                    last_call_at=int(e.get("last_call_at", 0)),
                    last_ok_at=int(e.get("last_ok_at", 0)),
                    calls_last_minute=int(e.get("calls_last_minute", 0)),
                    errors_last_minute=int(e.get("errors_last_minute", 0)),
                    avg_latency_ms=int(e.get("avg_latency_ms", 0)),
                    last_error=str(e.get("last_error", "")),
                )
                for e in entries
            ]
        )


def build_status_server_with_stats(
    status_provider: Callable[[], CoreStatus],
    stats_provider: Callable[[], Any] | None = None,
) -> grpc.aio.Server:
    """Build the aio gRPC server with the Status service (stats optional)."""
    server = grpc.aio.server()
    status_pb2_grpc.add_StatusServicer_to_server(
        _StatusServicerUpstream(status_provider, stats_provider), server
    )
    return server


async def fetch_upstream_stats(uri: str, timeout_s: float = 5.0) -> list[dict[str, Any]]:
    """Fetch one process's upstream call stats over the Status contract.

    The generic client of the providers panel: any process that binds
    the Status service answers (an empty list when it records nothing).
    """
    async with grpc.aio.insecure_channel(uri) as channel:
        stub = status_pb2_grpc.StatusStub(channel)
        reply = await stub.GetUpstreamStats(status_pb2.UpstreamStatsRequest(), timeout=timeout_s)
        return [
            {
                "provider_id": e.provider_id,
                "upstream": e.upstream,
                "ok": e.ok,
                "never_called": e.never_called,
                "total_calls": e.total_calls,
                "total_errors": e.total_errors,
                "consecutive_failures": e.consecutive_failures,
                "last_call_at": e.last_call_at,
                "last_ok_at": e.last_ok_at,
                "calls_last_minute": e.calls_last_minute,
                "errors_last_minute": e.errors_last_minute,
                "avg_latency_ms": e.avg_latency_ms,
                "last_error": e.last_error,
            }
            for e in reply.entries
        ]
