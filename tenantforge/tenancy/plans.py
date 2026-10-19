from __future__ import annotations

from dataclasses import dataclass

from .models import Organization, Plan


@dataclass(frozen=True)
class PlanLimits:
    max_projects: int
    max_seats: int


PLAN_LIMITS: dict[str, PlanLimits] = {
    Plan.FREE: PlanLimits(max_projects=3, max_seats=3),
    Plan.PRO: PlanLimits(max_projects=100, max_seats=50),
}


def limits_for(organization: Organization) -> PlanLimits:
    return PLAN_LIMITS[organization.plan]
