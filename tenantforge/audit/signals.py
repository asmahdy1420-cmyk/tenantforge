"""Write an AuditLog row whenever a registered model is created, updated or deleted."""

from __future__ import annotations

from typing import Any

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.db.models.signals import post_delete, post_save

from tenantforge.tenancy.context import get_current_actor
from tenantforge.tenancy.models import Organization

from .models import AuditLog

DEFAULT_AUDITED_MODELS = {
    "projects.Project": "project",
    "projects.Task": "task",
    "tenancy.Membership": "membership",
    "tenancy.ApiKey": "api_key",
}


def record(instance: Model, action: str) -> AuditLog:
    actor = get_current_actor()
    metadata: dict[str, Any] = {"repr": str(instance)[:200]}
    user = None
    if isinstance(actor, get_user_model()):
        user = actor
    elif actor is not None and hasattr(actor, "api_key"):
        metadata["api_key"] = actor.api_key.prefix
    return AuditLog.all_tenants.create(
        organization_id=instance.organization_id,
        actor=user,
        action=action,
        target_type=instance._meta.label_lower,
        target_id=str(instance.pk),
        metadata=metadata,
    )


def register(model: type[Model], name: str) -> None:
    def on_save(sender: type[Model], instance: Model, created: bool, **kwargs: Any) -> None:
        record(instance, f"{name}.{'created' if created else 'updated'}")

    def on_delete(sender: type[Model], instance: Model, **kwargs: Any) -> None:
        # Skip rows removed by an organization-level cascade: there is no tenant left
        # to attach the entry to.
        if Organization.objects.filter(pk=instance.organization_id).exists():
            record(instance, f"{name}.deleted")

    uid = f"audit.{model._meta.label_lower}"
    post_save.connect(on_save, sender=model, weak=False, dispatch_uid=f"{uid}.save")
    post_delete.connect(on_delete, sender=model, weak=False, dispatch_uid=f"{uid}.delete")


def connect_default_models() -> None:
    for label, name in DEFAULT_AUDITED_MODELS.items():
        register(apps.get_model(label), name)
