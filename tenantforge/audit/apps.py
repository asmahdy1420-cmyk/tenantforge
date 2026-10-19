from __future__ import annotations

from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tenantforge.audit"
    label = "audit"

    def ready(self) -> None:
        from . import signals

        signals.connect_default_models()
