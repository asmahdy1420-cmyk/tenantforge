"""Roles, API key lifecycle, plan limits, audit log and tenant-aware Celery tasks."""

from __future__ import annotations

import pytest

from tenantforge.audit.models import AuditLog
from tenantforge.projects.models import Project, Task
from tenantforge.projects.tasks import summarize_project
from tenantforge.tenancy.context import get_current_tenant, tenant_context
from tenantforge.tenancy.models import ApiKey, Plan

pytestmark = pytest.mark.django_db


def test_member_can_read_but_not_create_projects(api, acme_member, acme_project):
    client = api(acme_member, "acme")
    assert client.get("/api/projects/").status_code == 200
    assert client.post("/api/projects/", {"name": "Nope"}).status_code == 403


def test_member_can_create_tasks(api, acme_member, acme_project):
    response = api(acme_member, "acme").post(
        "/api/tasks/", {"project": acme_project.pk, "title": "Write docs"}
    )
    assert response.status_code == 201
    task = Task.all_tenants.get(pk=response.data["id"])
    assert task.organization_id == acme_project.organization_id


def test_admin_creates_project_and_duplicate_name_is_rejected(api, alice, acme):
    client = api(alice, "acme")
    assert client.post("/api/projects/", {"name": "Alpha"}).status_code == 201
    response = client.post("/api/projects/", {"name": "Alpha"})
    assert response.status_code == 400
    assert "name" in response.data


def test_api_key_raw_value_is_returned_once(api, alice, acme_member, acme):
    assert api(acme_member, "acme").post("/api/api-keys/", {"name": "x"}).status_code == 403

    client = api(alice, "acme")
    created = client.post("/api/api-keys/", {"name": "deploy", "role": "admin"})
    assert created.status_code == 201
    raw_key = created.data["key"]
    assert raw_key.startswith(f"tf_{created.data['prefix']}_")

    listed = client.get("/api/api-keys/").data["results"]
    assert "key" not in listed[0]
    stored = ApiKey.all_tenants.get(pk=created.data["id"])
    assert raw_key not in stored.key_hash


def test_free_plan_project_limit(api, alice, acme):
    client = api(alice, "acme")
    for i in range(3):
        assert client.post("/api/projects/", {"name": f"P{i}"}).status_code == 201
    response = client.post("/api/projects/", {"name": "P3"})
    assert response.status_code == 403
    assert response.data["code"] == "plan_limit_exceeded"

    acme.plan = Plan.PRO
    acme.save()
    assert client.post("/api/projects/", {"name": "P3"}).status_code == 201


def test_seat_limit_and_owner_only_rules(api, alice, acme, make_user):
    client = api(alice, "acme")
    for name in ("u1", "u2", "u3"):
        make_user(name)
    assert client.post("/api/members/", {"username": "u1"}).status_code == 201
    assert client.post("/api/members/", {"username": "u2", "role": "admin"}).status_code == 201
    response = client.post("/api/members/", {"username": "u3"})
    assert response.status_code == 403
    assert response.data["limit"] == "seats"


def test_last_owner_cannot_be_removed(api, alice, acme):
    client = api(alice, "acme")
    owner_membership = client.get("/api/members/").data["results"][0]
    assert client.delete(f"/api/members/{owner_membership['id']}/").status_code == 400


def test_audit_log_records_actor_and_is_tenant_scoped(api, alice, bob, acme, globex):
    api(alice, "acme").post("/api/projects/", {"name": "Audited"})
    api(bob, "globex").post("/api/projects/", {"name": "Other"})

    response = api(alice, "acme").get("/api/audit-logs/", {"action": "project.created"})
    assert response.status_code == 200
    entries = response.data["results"]
    assert len(entries) == 1
    assert entries[0]["actor"] == alice.pk
    assert entries[0]["metadata"]["repr"] == "Audited"


def test_member_cannot_read_audit_log(api, acme_member):
    assert api(acme_member, "acme").get("/api/audit-logs/").status_code == 403


def test_celery_task_runs_in_the_given_tenant(acme, acme_project):
    with tenant_context(acme):
        Task.objects.create(project=acme_project, title="a")
        Task.objects.create(project=acme_project, title="b", status=Task.Status.DONE)

    result = summarize_project.delay(acme.pk, acme_project.pk).get()
    assert result == {
        "organization": "acme",
        "project_id": acme_project.pk,
        "total": 2,
        "by_status": {"todo": 1, "done": 1},
    }
    assert get_current_tenant() is None


def test_celery_task_cannot_reach_other_tenant_rows(acme, globex_project):
    with pytest.raises(Project.DoesNotExist):
        summarize_project.delay(acme.pk, globex_project.pk).get()


def test_summarize_endpoint_queues_tenant_task(api, acme_member, acme_project):
    response = api(acme_member, "acme").post(f"/api/projects/{acme_project.pk}/summarize/")
    assert response.status_code == 202
    assert response.data["result"]["total"] == 0


def test_current_organization_reports_usage(api, alice, acme, acme_project):
    response = api(alice, "acme").get("/api/organizations/current/")
    assert response.status_code == 200
    assert response.data["role"] == "owner"
    assert response.data["usage"] == {
        "projects": 1,
        "max_projects": 3,
        "seats": 1,
        "max_seats": 3,
    }


def test_audit_entries_exist_per_tenant(acme, globex, acme_project, globex_project):
    with tenant_context(acme):
        actions = set(AuditLog.objects.values_list("action", flat=True))
    assert actions == {"membership.created", "project.created"}
