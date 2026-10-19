from __future__ import annotations

from django.conf import settings
from django.db import models

from tenantforge.tenancy.models import TenantScopedModel


class AuditLog(TenantScopedModel):
    """Append-only record of changes to tenant data."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["organization", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.action} {self.target_type}:{self.target_id}"
