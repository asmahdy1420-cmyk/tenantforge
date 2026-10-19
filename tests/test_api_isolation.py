"""Tenant isolation over HTTP: resolution, membership and object access."""

from __future__ import annotations

import pytest

from tenantforge.projects.models import Task
from tenantforge.tenancy.context import tenant_context
from tenantforge.tenancy.models import ApiKey

pytestmark = pytest.mark.django_db


def test_list_returns_only_current_tenant_rows(api, alice, acme_project, globex_project):
    response = api(alice, "acme").get("/api/projects/")
    assert response.status_code == 200
    assert [p["name"] for p in response.data["results"]] == ["Acme roadmap"]


def test_non_member_cannot_use_another_tenant(api, alice, acme, globex_project):
    response = api(alice, "globex").get("/api/projects/")
    assert response.status_code == 403


def test_object_of_other_tenant_is_not_found(api, alice, acme, globex_project, globex_task):
    client = api(alice, "acme")
    assert client.get(f"/api/projects/{globex_project.pk}/").status_code == 404
    assert client.patch(f"/api/tasks/{globex_task.pk}/", {"title": "x"}).status_code == 404
    assert client.delete(f"/api/tasks/{globex_task.pk}/").status_code == 404
    with tenant_context(globex_project.organization):
        assert Task.objects.get(pk=globex_task.pk).title == "Launch plan"


def test_cannot_create_task_in_project_of_other_tenant(api, alice, acme, globex_project):
    response = api(alice, "acme").post(
        "/api/tasks/", {"project": globex_project.pk, "title": "Injected"}
    )
    assert response.status_code == 400
    assert "project" in response.data
    assert not Task.all_tenants.filter(title="Injected").exists()


def test_tenant_resolved_from_subdomain(api, alice, acme_project):
    response = api(alice).get("/api/projects/", HTTP_HOST="acme.example.test")
    assert response.status_code == 200
    assert response.data["count"] == 1


def test_unknown_tenant_is_404_and_missing_tenant_is_400(api, alice, acme):
    assert api(alice, "nope").get("/api/projects/").status_code == 404
    response = api(alice).get("/api/projects/")
    assert response.status_code == 400
    assert response.data["detail"].code == "tenant_required"


def test_api_key_pins_its_tenant(api, acme, globex, acme_project):
    with tenant_context(acme):
        _, raw_key = ApiKey.issue(name="ci")
    client = api()
    client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")
    response = client.get("/api/projects/")
    assert response.status_code == 200
    assert response.data["count"] == 1

    client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}", HTTP_X_TENANT="globex")
    assert client.get("/api/projects/").status_code == 401


def test_revoked_or_wrong_key_is_rejected(api, alice, acme):
    with tenant_context(acme):
        api_key, raw_key = ApiKey.issue(name="old")
    client = api(alice, "acme")
    assert client.delete(f"/api/api-keys/{api_key.pk}/").status_code == 204

    anon = api()
    anon.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")
    assert anon.get("/api/projects/").status_code == 401
    anon.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key[:-2]}xx")
    assert anon.get("/api/projects/").status_code == 401


def test_unauthenticated_request_is_401(api, acme):
    assert api(tenant="acme").get("/api/projects/").status_code == 401


def test_organization_list_shows_only_my_orgs(api, alice, acme, globex):
    response = api(alice).get("/api/organizations/")
    assert [org["slug"] for org in response.data] == ["acme"]
