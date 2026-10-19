"""Request-scoped tenant state held in context variables.

Context variables are isolated per thread and per asyncio task, so a tenant set
while handling one request never leaks into another one running concurrently.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import Organization

_current_tenant: ContextVar[Organization | None] = ContextVar(
    "tenantforge_current_tenant", default=None
)
_unscoped: ContextVar[bool] = ContextVar("tenantforge_unscoped", default=False)
_current_actor: ContextVar[Any] = ContextVar("tenantforge_current_actor", default=None)


def get_current_tenant() -> Organization | None:
    return _current_tenant.get()


def set_current_tenant(tenant: Organization | None) -> Token:
    return _current_tenant.set(tenant)


def reset_current_tenant(token: Token) -> None:
    _current_tenant.reset(token)


def is_unscoped() -> bool:
    return _unscoped.get()


def get_current_actor() -> Any:
    return _current_actor.get()


def set_current_actor(actor: Any) -> Token:
    return _current_actor.set(actor)


def reset_current_actor(token: Token) -> None:
    _current_actor.reset(token)


@contextmanager
def tenant_context(tenant: Organization | None) -> Iterator[Organization | None]:
    """Run a block of code as ``tenant``. The previous tenant is restored on exit."""
    token = _current_tenant.set(tenant)
    try:
        yield tenant
    finally:
        _current_tenant.reset(token)


@contextmanager
def unscoped() -> Iterator[None]:
    """Explicitly opt out of tenant filtering (migrations, platform admin, reports)."""
    token = _unscoped.set(True)
    try:
        yield
    finally:
        _unscoped.reset(token)
