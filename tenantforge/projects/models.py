from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models

from tenantforge.tenancy.exceptions import CrossTenantWriteError
from tenantforge.tenancy.models import TenantScopedModel


class Project(TenantScopedModel):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_project_name_per_org"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Task(TenantScopedModel):
    class Status(models.TextChoices):
        TODO = "todo", "To do"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TODO)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["organization", "project", "status"])]

    def __str__(self) -> str:
        return self.title

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.enforce_tenant()
        # Defence in depth: a task may only point at a project of its own tenant.
        if self.project.organization_id != self.organization_id:
            raise CrossTenantWriteError("Task and project belong to different organizations.")
        super().save(*args, **kwargs)
