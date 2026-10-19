"""Translate tenancy domain exceptions into HTTP responses."""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .exceptions import CrossTenantWriteError, PlanLimitExceeded, TenantNotSetError


class TenantRequired(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This endpoint requires a tenant (X-Tenant header or tenant subdomain)."
    default_code = "tenant_required"


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, PlanLimitExceeded):
        return Response(
            {
                "detail": str(exc),
                "code": "plan_limit_exceeded",
                "limit": exc.limit,
                "maximum": exc.maximum,
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    if isinstance(exc, CrossTenantWriteError):
        return Response(
            {"detail": "Cross-tenant write rejected.", "code": "cross_tenant_write"},
            status=status.HTTP_403_FORBIDDEN,
        )
    if isinstance(exc, TenantNotSetError):
        exc = TenantRequired()
    return drf_exception_handler(exc, context)
