from __future__ import annotations

from django.db.models import QuerySet
from rest_framework import viewsets

from tenantforge.tenancy.models import Role
from tenantforge.tenancy.views import TenantAPIMixin

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(TenantAPIMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    read_role = Role.ADMIN

    def get_queryset(self) -> QuerySet[AuditLog]:
        queryset = AuditLog.objects.all()
        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)
        return queryset
