from __future__ import annotations

from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

from .context import (
    reset_current_actor,
    reset_current_tenant,
    set_current_actor,
    set_current_tenant,
)
from .models import Organization

TENANT_HEADER = "X-Tenant"


def subdomain_from_host(host: str, base_domain: str) -> str | None:
    """Return ``acme`` for ``acme.example.com`` when the base domain is ``example.com``."""
    host = host.split(":", 1)[0].lower()
    base_domain = base_domain.lower().lstrip(".")
    if not base_domain or not host.endswith("." + base_domain):
        return None
    sub = host[: -(len(base_domain) + 1)]
    if not sub or "." in sub or sub in settings.TENANT_RESERVED_SUBDOMAINS:
        return None
    return sub


def resolve_tenant_slug(request: HttpRequest) -> str | None:
    header = request.headers.get(TENANT_HEADER, "").strip()
    if header:
        return header.lower()
    return subdomain_from_host(request.get_host(), settings.TENANT_BASE_DOMAIN)


class TenantMiddleware:
    """Resolve the tenant for the request and bind it to the current context.

    The header wins over the subdomain. An unknown tenant is a 404 so that the
    response does not reveal whether a slug exists elsewhere. Whatever the view
    does to the context is undone when the response leaves the middleware.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        slug = resolve_tenant_slug(request)
        tenant = None
        if slug:
            tenant = Organization.objects.filter(slug=slug).first()
            if tenant is None:
                return JsonResponse(
                    {"detail": "Unknown tenant.", "code": "unknown_tenant"}, status=404
                )
        request.tenant = tenant
        tenant_token = set_current_tenant(tenant)
        actor_token = set_current_actor(None)
        try:
            return self.get_response(request)
        finally:
            reset_current_actor(actor_token)
            reset_current_tenant(tenant_token)
