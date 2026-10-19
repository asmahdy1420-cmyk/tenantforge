"""Tenant isolation at the ORM layer: the manager, the model mixin and bulk writes."""

from __future__ import annotations

import pytest

from tenantforge.projects.models import Project, Task
from tenantforge.tenancy.context import get_current_tenant, tenant_context, unscoped
from tenantforge.tenancy.exceptions import CrossTenantWriteError, TenantNotSetError

pytestmark = pytest.mark.django_db


def test_query_without_tenant_is_refused(acme_project):
    with pytest.raises(TenantNotSetError):
        list(Project.objects.all())


def test_queries_only_see_the_active_tenant(acme, acme_project, globex_project):
    with tenant_context(acme):
        assert list(Project.objects.values_list("name", flat=True)) == ["Acme roadmap"]


def test_get_by_id_of_other_tenant_raises_does_not_exist(acme, globex_project):
    with tenant_context(acme), pytest.raises(Project.DoesNotExist):
        Project.objects.get(pk=globex_project.pk)


def test_create_assigns_active_tenant(acme):
    with tenant_context(acme):
        project = Project.objects.create(name="New")
    assert project.organization_id == acme.pk


def test_create_without_tenant_is_refused(db):
    with pytest.raises(TenantNotSetError):
        Project(name="Orphan").save()


def test_saving_another_tenants_row_is_refused(acme, globex_project):
    globex_project.name = "Hijacked"
    with tenant_context(acme), pytest.raises(CrossTenantWriteError):
        globex_project.save()
    with unscoped():
        assert Project.objects.get(pk=globex_project.pk).name == "Globex secrets"


def test_deleting_another_tenants_row_is_refused(acme, globex_project):
    with tenant_context(acme), pytest.raises(CrossTenantWriteError):
        globex_project.delete()
    assert Project.all_tenants.filter(pk=globex_project.pk).exists()


def test_bulk_update_and_delete_stay_inside_tenant(acme, acme_project, globex_project):
    with tenant_context(acme):
        assert Project.objects.update(description="touched") == 1
        assert Project.objects.all().delete()[0] >= 1
    globex_project.refresh_from_db()
    assert globex_project.description == ""


def test_bulk_create_rejects_rows_for_another_tenant(acme, globex):
    with tenant_context(acme), pytest.raises(CrossTenantWriteError):
        Project.objects.bulk_create([Project(name="Sneaky", organization=globex)])


def test_task_cannot_point_at_project_of_another_tenant(acme, globex_project):
    with tenant_context(acme), pytest.raises(CrossTenantWriteError):
        Task.objects.create(project=globex_project, title="Cross link", organization=acme)


def test_unscoped_and_context_reset(acme, acme_project, globex_project):
    with unscoped():
        assert Project.objects.count() == 2
    with tenant_context(acme):
        assert get_current_tenant() == acme
    assert get_current_tenant() is None
