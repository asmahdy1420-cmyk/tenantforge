"""Domain exceptions. Kept free of DRF imports so models can depend on them."""

from __future__ import annotations


class TenantNotSetError(RuntimeError):
    """A tenant-scoped query or write was attempted without an active tenant."""


class CrossTenantWriteError(RuntimeError):
    """An object belonging to one tenant was written while another tenant is active."""


class PlanLimitExceeded(Exception):
    def __init__(self, limit: str, maximum: int) -> None:
        self.limit = limit
        self.maximum = maximum
        super().__init__(f"Plan limit reached for {limit} (maximum {maximum}).")
