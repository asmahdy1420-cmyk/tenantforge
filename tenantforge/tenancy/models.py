from __future__ import annotations

import hashlib
import secrets
from typing import Any

from django.conf import settings
from django.db import models

from .context import get_current_tenant, is_unscoped
from .exceptions import CrossTenantWriteError, TenantNotSetError
from .managers import TenantScopedManager


class Plan(models.TextChoices):
    FREE = "free", "Free"
    PRO = "pro", "Pro"


class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"


ROLE_RANK = {Role.MEMBER: 1, Role.ADMIN: 2, Role.OWNER: 3}


def role_at_least(role: str | None, required: str) -> bool:
    if role is None:
        return False
    return ROLE_RANK[Role(role)] >= ROLE_RANK[Role(required)]


class Organization(models.Model):
    """The tenant. Every tenant-owned row carries a foreign key to one of these."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=63, unique=True)
    plan = models.CharField(max_length=16, choices=Plan.choices, default=Plan.FREE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Membership(models.Model):
    """Links a user to an organization with a role.

    Memberships are read across tenants (a user lists their organizations), so
    this model is filtered explicitly rather than through TenantScopedManager.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "organization"], name="unique_membership"),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization} ({self.role})"


class TenantScopedModel(models.Model):
    """Abstract base for tenant-owned data.

    - ``objects`` is scoped to the active tenant and refuses unscoped reads.
    - ``all_tenants`` is an explicit escape hatch for platform-level code.
    - ``save()``/``delete()`` refuse to touch rows that belong to another tenant.
    """

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="+", editable=False
    )

    objects = TenantScopedManager()
    all_tenants = models.Manager()  # noqa: DJ012 (explicit unscoped manager)

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.enforce_tenant()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        self.enforce_tenant()
        return super().delete(*args, **kwargs)

    def enforce_tenant(self) -> None:
        tenant = get_current_tenant()
        if self.organization_id is None:
            if tenant is None:
                raise TenantNotSetError(
                    f"Cannot save {type(self).__name__} without an active tenant."
                )
            self.organization = tenant
            return
        if tenant is not None and not is_unscoped() and self.organization_id != tenant.pk:
            raise CrossTenantWriteError(
                f"{type(self).__name__} belongs to organization {self.organization_id}, "
                f"active tenant is {tenant.pk}."
            )


def hash_api_key(raw_key: str) -> str:
    # API keys carry 256 bits of randomness, so a fast hash is sufficient;
    # slow password hashers would only add latency to every request.
    return hashlib.sha256(raw_key.encode()).hexdigest()


class ApiKey(TenantScopedModel):
    """A per-tenant API key. Only the SHA-256 hash and a short public prefix are stored."""

    ROLE_CHOICES = [(Role.ADMIN, "Admin"), (Role.MEMBER, "Member")]

    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=16, unique=True)
    key_hash = models.CharField(max_length=64)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=Role.MEMBER)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix})"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    @classmethod
    def issue(
        cls, *, name: str, role: str = Role.MEMBER, created_by: Any = None
    ) -> tuple[ApiKey, str]:
        """Create a key for the active tenant. Returns the model and the raw key (shown once)."""
        prefix = secrets.token_hex(4)
        raw_key = f"tf_{prefix}_{secrets.token_urlsafe(32)}"
        api_key = cls.objects.create(
            name=name,
            prefix=prefix,
            key_hash=hash_api_key(raw_key),
            role=role,
            created_by=created_by,
        )
        return api_key, raw_key
