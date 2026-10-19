from __future__ import annotations

from typing import Any

from django.db.models import Count

from tenantforge.tenancy.context import get_current_tenant
from tenantforge.tenancy.tasks import tenant_task

from .models import Project, Task


@tenant_task()
def summarize_project(project_id: int) -> dict[str, Any]:
    """Count a project's tasks by status. Runs inside the tenant passed by the caller."""
    project = Project.objects.get(pk=project_id)
    rows = Task.objects.filter(project=project).values("status").annotate(total=Count("id"))
    by_status = {row["status"]: row["total"] for row in rows}
    tenant = get_current_tenant()
    return {
        "organization": tenant.slug if tenant else None,
        "project_id": project.pk,
        "total": sum(by_status.values()),
        "by_status": by_status,
    }
