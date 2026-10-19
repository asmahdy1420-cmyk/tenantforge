"""Helpers for Celery tasks that run inside one tenant."""

from __future__ import annotations

import functools
from typing import Any, Callable

from celery import shared_task

from .context import tenant_context
from .models import Organization


def tenant_task(**task_options: Any) -> Callable[[Callable[..., Any]], Any]:
    """Register a Celery task whose first argument is an organization id.

    Workers have no request, so the tenant travels as a plain id and is bound to
    the context for the duration of the task::

        @tenant_task()
        def rebuild_index(project_id): ...

        rebuild_index.delay(org.pk, project.pk)
    """

    def decorator(func: Callable[..., Any]) -> Any:
        @functools.wraps(func)
        def run(organization_id: int, *args: Any, **kwargs: Any) -> Any:
            organization = Organization.objects.get(pk=organization_id)
            with tenant_context(organization):
                return func(*args, **kwargs)

        task_options.setdefault("name", f"{func.__module__}.{func.__name__}")
        return shared_task(**task_options)(run)

    return decorator
