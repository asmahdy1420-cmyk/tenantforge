from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from tenantforge.audit.views import AuditLogViewSet
from tenantforge.projects.views import ProjectViewSet, TaskViewSet
from tenantforge.tenancy.views import (
    ApiKeyViewSet,
    CurrentOrganizationView,
    MembershipViewSet,
    OrganizationListCreateView,
)

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("tasks", TaskViewSet, basename="task")
router.register("members", MembershipViewSet, basename="member")
router.register("api-keys", ApiKeyViewSet, basename="api-key")
router.register("audit-logs", AuditLogViewSet, basename="audit-log")


def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("api/organizations/", OrganizationListCreateView.as_view(), name="organization-list"),
    path(
        "api/organizations/current/",
        CurrentOrganizationView.as_view(),
        name="organization-current",
    ),
    path("api/", include(router.urls)),
]
