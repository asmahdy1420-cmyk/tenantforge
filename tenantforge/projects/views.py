from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from tenantforge.tenancy.models import Role
from tenantforge.tenancy.views import TenantAPIMixin

from .models import Project, Task
from .serializers import ProjectSerializer, TaskSerializer
from .services import create_project
from .tasks import summarize_project


def _user_or_none(request: Request) -> object | None:
    return request.user if isinstance(request.user, get_user_model()) else None


class ProjectViewSet(TenantAPIMixin, viewsets.ModelViewSet):
    """Projects of the active tenant. Members read; admins and owners write."""

    serializer_class = ProjectSerializer
    read_role = Role.MEMBER
    write_role = Role.ADMIN

    def required_role(self, request: Request) -> str:
        if self.action == "summarize":
            return Role.MEMBER
        return super().required_role(request)

    # No class-level ``queryset``: Project.objects must be evaluated per request,
    # after the tenant is bound, never at import time.
    def get_queryset(self) -> QuerySet[Project]:
        return Project.objects.all()

    def perform_create(self, serializer: serializers.BaseSerializer) -> None:
        serializer.instance = create_project(
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description", ""),
            created_by=_user_or_none(self.request),
        )

    @action(detail=True, methods=["post"])
    def summarize(self, request: Request, pk: str | None = None) -> Response:
        project = self.get_object()
        result = summarize_project.delay(request.tenant.pk, project.pk)
        body = {"task_id": result.id, "status": result.status}
        if result.ready():
            body["result"] = result.result
        return Response(body, status=status.HTTP_202_ACCEPTED)


class TaskViewSet(TenantAPIMixin, viewsets.ModelViewSet):
    """Tasks of the active tenant. Any member can create and update tasks."""

    serializer_class = TaskSerializer
    read_role = Role.MEMBER
    write_role = Role.MEMBER

    def get_queryset(self) -> QuerySet[Task]:
        queryset = Task.objects.select_related("project")
        project = self.request.query_params.get("project")
        if project:
            queryset = queryset.filter(project_id=project)
        task_status = self.request.query_params.get("status")
        if task_status:
            queryset = queryset.filter(status=task_status)
        return queryset
