from __future__ import annotations

import hmac
from typing import Any

from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.request import Request

from .context import set_current_tenant
from .models import ApiKey, hash_api_key


class ApiKeyPrincipal:
    """The authenticated identity for a request made with an API key."""

    is_authenticated = True
    is_anonymous = False
    is_active = True
    is_staff = False
    is_superuser = False
    pk = None
    id = None

    def __init__(self, api_key: ApiKey) -> None:
        self.api_key = api_key

    def __str__(self) -> str:
        return f"api-key:{self.api_key.prefix}"


class ApiKeyAuthentication(BaseAuthentication):
    """``Authorization: Api-Key tf_<prefix>_<secret>``.

    The key pins the request to its organization. If the request already named
    a different tenant (header or subdomain) authentication fails.
    """

    keyword = "Api-Key"

    def authenticate(self, request: Request) -> tuple[ApiKeyPrincipal, ApiKey] | None:
        parts = get_authorization_header(request).split()
        if not parts or parts[0].decode().lower() != self.keyword.lower():
            return None
        if len(parts) != 2:
            raise exceptions.AuthenticationFailed("Invalid API key header.")
        raw_key = parts[1].decode()
        try:
            _, prefix, _ = raw_key.split("_", 2)
        except ValueError:
            raise exceptions.AuthenticationFailed("Invalid API key.") from None

        api_key = (
            ApiKey.all_tenants.select_related("organization")
            .filter(prefix=prefix, revoked_at__isnull=True)
            .first()
        )
        if api_key is None or not hmac.compare_digest(api_key.key_hash, hash_api_key(raw_key)):
            raise exceptions.AuthenticationFailed("Invalid API key.")

        django_request: Any = request._request
        tenant = getattr(django_request, "tenant", None)
        if tenant is not None and tenant.pk != api_key.organization_id:
            raise exceptions.AuthenticationFailed("API key does not belong to this tenant.")
        if tenant is None:
            django_request.tenant = api_key.organization
            set_current_tenant(api_key.organization)

        ApiKey.all_tenants.filter(pk=api_key.pk).update(last_used_at=timezone.now())
        return ApiKeyPrincipal(api_key), api_key

    def authenticate_header(self, request: Request) -> str:
        return self.keyword
