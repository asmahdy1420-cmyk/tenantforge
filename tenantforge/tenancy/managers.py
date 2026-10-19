from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.db import models

from .context import get_current_tenant, is_unscoped
from .exceptions import TenantNotSetError


class TenantScopedQuerySet(models.QuerySet):
    def bulk_create(self, objs: Iterable[Any], *args: Any, **kwargs: Any) -> list[Any]:
        # bulk_create bypasses Model.save(), so the tenant guard runs here instead.
        objs = list(objs)
        for obj in objs:
            obj.enforce_tenant()
        return super().bulk_create(objs, *args, **kwargs)


class TenantScopedManager(models.Manager.from_queryset(TenantScopedQuerySet)):
    """Default manager for tenant-owned models.

    Every queryset is filtered by the active tenant. With no active tenant the
    manager raises instead of silently returning rows from every tenant.
    """

    def get_queryset(self) -> TenantScopedQuerySet:
        queryset = super().get_queryset()
        if is_unscoped():
            return queryset
        tenant = get_current_tenant()
        if tenant is None:
            raise TenantNotSetError(
                f"{self.model.__name__} queried without an active tenant. "
                "Wrap the code in tenant_context(org) or unscoped()."
            )
        return queryset.filter(organization=tenant)
