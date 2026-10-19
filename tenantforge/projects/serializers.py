from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from rest_framework import serializers

from tenantforge.tenancy.context import get_current_tenant

from .models import Project, Task


class TenantMemberField(serializers.PrimaryKeyRelatedField):
    """Accept only users who are members of the active tenant."""

    def get_queryset(self) -> QuerySet[Any]:
        return get_user_model().objects.filter(memberships__organization=get_current_tenant())


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "description", "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate_name(self, value: str) -> str:
        clash = Project.objects.filter(name=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("A project with this name already exists.")
        return value


class TaskSerializer(serializers.ModelSerializer):
    # Passing the manager (not .all()) keeps the queryset lazy, so it is
    # evaluated per request against the active tenant.
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects)
    assignee = TenantMemberField(required=False, allow_null=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "project",
            "title",
            "status",
            "assignee",
            "due_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
