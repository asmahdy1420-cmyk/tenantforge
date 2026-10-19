from __future__ import annotations

from typing import Any

from django.db import transaction

from tenantforge.tenancy.context import get_current_tenant
from tenantforge.tenancy.exceptions import PlanLimitExceeded, TenantNotSetError
from tenantforge.tenancy.plans import limits_for
from tenantforge.tenancy.services import lock_organization

from .models import Project


@transaction.atomic
def create_project(*, name: str, description: str = "", created_by: Any = None) -> Project:
    """Create a project in the active tenant, enforcing the plan's project limit."""
    tenant = get_current_tenant()
    if tenant is None:
        raise TenantNotSetError("create_project requires an active tenant.")
    organization = lock_organization(tenant)
    limits = limits_for(organization)
    if Project.objects.count() >= limits.max_projects:
        raise PlanLimitExceeded("projects", limits.max_projects)
    return Project.objects.create(name=name, description=description, created_by=created_by)
