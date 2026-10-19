"""Write paths for organizations and memberships. Business rules live here, not in views."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from .exceptions import PlanLimitExceeded
from .models import Membership, Organization, Plan, Role
from .plans import limits_for


class MembershipError(ValueError):
    pass


@transaction.atomic
def create_organization(*, name: str, slug: str, owner: Any, plan: str = Plan.FREE) -> Organization:
    organization = Organization.objects.create(name=name, slug=slug.lower(), plan=plan)
    Membership.objects.create(user=owner, organization=organization, role=Role.OWNER)
    return organization


def lock_organization(organization: Organization) -> Organization:
    """Lock the tenant row so concurrent limit checks are serialised (PostgreSQL)."""
    return Organization.objects.select_for_update().get(pk=organization.pk)


@transaction.atomic
def add_member(*, organization: Organization, user: Any, role: str = Role.MEMBER) -> Membership:
    organization = lock_organization(organization)
    if Membership.objects.filter(organization=organization, user=user).exists():
        raise MembershipError("User is already a member of this organization.")
    seats = Membership.objects.filter(organization=organization).count()
    limits = limits_for(organization)
    if seats >= limits.max_seats:
        raise PlanLimitExceeded("seats", limits.max_seats)
    return Membership.objects.create(organization=organization, user=user, role=role)


@transaction.atomic
def remove_member(*, membership: Membership) -> None:
    if membership.role == Role.OWNER:
        owners = Membership.objects.filter(
            organization_id=membership.organization_id, role=Role.OWNER
        ).count()
        if owners <= 1:
            raise MembershipError("An organization must keep at least one owner.")
    membership.delete()
