from __future__ import annotations

from typing import Any, Callable

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from tenantforge.projects.models import Project, Task
from tenantforge.tenancy.context import tenant_context
from tenantforge.tenancy.models import Organization, Role
from tenantforge.tenancy.services import add_member, create_organization


@pytest.fixture
def make_user(db: Any) -> Callable[[str], Any]:
    def make(username: str) -> Any:
        return get_user_model().objects.create_user(username=username, password="s3cret-pass!")

    return make


@pytest.fixture
def alice(make_user: Callable[[str], Any]) -> Any:
    return make_user("alice")


@pytest.fixture
def bob(make_user: Callable[[str], Any]) -> Any:
    return make_user("bob")


@pytest.fixture
def acme(alice: Any) -> Organization:
    """Tenant A, owned by alice."""
    return create_organization(name="Acme", slug="acme", owner=alice)


@pytest.fixture
def globex(bob: Any) -> Organization:
    """Tenant B, owned by bob."""
    return create_organization(name="Globex", slug="globex", owner=bob)


@pytest.fixture
def acme_member(make_user: Callable[[str], Any], acme: Organization) -> Any:
    user = make_user("carol")
    add_member(organization=acme, user=user, role=Role.MEMBER)
    return user


@pytest.fixture
def acme_project(acme: Organization) -> Project:
    with tenant_context(acme):
        return Project.objects.create(name="Acme roadmap")


@pytest.fixture
def globex_project(globex: Organization) -> Project:
    with tenant_context(globex):
        return Project.objects.create(name="Globex secrets")


@pytest.fixture
def globex_task(globex: Organization, globex_project: Project) -> Task:
    with tenant_context(globex):
        return Task.objects.create(project=globex_project, title="Launch plan")


@pytest.fixture
def api() -> Callable[..., APIClient]:
    def client_for(user: Any = None, tenant: str | None = None) -> APIClient:
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        if tenant is not None:
            client.credentials(HTTP_X_TENANT=tenant)
        return client

    return client_for
