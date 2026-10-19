from __future__ import annotations

from typing import Any

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request

from .api_errors import TenantRequired
from .models import ApiKey, Membership, role_at_least


def get_request_role(request: Request) -> str | None:
    """The caller's role in the request's tenant, or None if they are not a member."""
    if hasattr(request, "_tenant_role"):
        return request._tenant_role
    tenant = getattr(request, "tenant", None)
    role = None
    if tenant is not None:
        if isinstance(request.auth, ApiKey):
            role = request.auth.role if request.auth.organization_id == tenant.pk else None
        elif request.user and request.user.is_authenticated:
            role = (
                Membership.objects.filter(user=request.user, organization=tenant)
                .values_list("role", flat=True)
                .first()
            )
    request._tenant_role = role
    return role


class HasTenantRole(BasePermission):
    """Require a tenant and a minimum role in it.

    The view decides the role through ``required_role(request)``; by default it
    reads ``read_role`` for safe methods and ``write_role`` otherwise.
    """

    message = "You do not have the required role in this organization."

    def has_permission(self, request: Request, view: Any) -> bool:
        if getattr(request, "tenant", None) is None:
            raise TenantRequired()
        role = get_request_role(request)
        if role is None:
            self.message = "You are not a member of this organization."
            return False
        if hasattr(view, "required_role"):
            required = view.required_role(request)
        else:
            required = "member" if request.method in SAFE_METHODS else "admin"
        return role_at_least(role, required)
