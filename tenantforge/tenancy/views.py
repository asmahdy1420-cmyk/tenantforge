from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, mixins, serializers, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .context import set_current_actor
from .models import ApiKey, Membership, Organization, Role, role_at_least
from .permissions import HasTenantRole, get_request_role
from .plans import limits_for
from .serializers import (
    ApiKeyCreateSerializer,
    ApiKeySerializer,
    MembershipCreateSerializer,
    MembershipSerializer,
    OrganizationSerializer,
)
from .services import MembershipError, add_member, create_organization, remove_member


class TenantAPIMixin:
    """Base behaviour for endpoints that operate inside one tenant."""

    permission_classes = [IsAuthenticated, HasTenantRole]
    read_role: str = Role.MEMBER
    write_role: str = Role.ADMIN

    def required_role(self, request: Request) -> str:
        return self.read_role if request.method in SAFE_METHODS else self.write_role

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)
        # Authentication has run; expose the caller to audit signal handlers.
        set_current_actor(request.user)


class OrganizationListCreateView(generics.ListCreateAPIView):
    """List the caller's organizations or create a new one (the caller becomes owner)."""

    serializer_class = OrganizationSerializer
    pagination_class = None

    def get_queryset(self) -> QuerySet[Organization]:
        if isinstance(self.request.auth, ApiKey):
            return Organization.objects.filter(pk=self.request.auth.organization_id)
        return Organization.objects.filter(memberships__user=self.request.user)

    def perform_create(self, serializer: serializers.BaseSerializer) -> None:
        if isinstance(self.request.auth, ApiKey):
            raise PermissionDenied("API keys cannot create organizations.")
        serializer.instance = create_organization(
            name=serializer.validated_data["name"],
            slug=serializer.validated_data["slug"],
            owner=self.request.user,
        )


class CurrentOrganizationView(TenantAPIMixin, APIView):
    def get(self, request: Request) -> Response:
        tenant = request.tenant
        from tenantforge.projects.models import Project

        limits = limits_for(tenant)
        data = OrganizationSerializer(tenant).data
        data["role"] = get_request_role(request)
        data["usage"] = {
            "projects": Project.objects.count(),
            "max_projects": limits.max_projects,
            "seats": Membership.objects.filter(organization=tenant).count(),
            "max_seats": limits.max_seats,
        }
        return Response(data)


class MembershipViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = MembershipSerializer

    def get_queryset(self) -> QuerySet[Membership]:
        return (
            Membership.objects.filter(organization=self.request.tenant)
            .select_related("user")
            .order_by("created_at")
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        payload = MembershipCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        role = payload.validated_data["role"]
        if role == Role.OWNER and get_request_role(request) != Role.OWNER:
            raise PermissionDenied("Only owners can add owners.")
        user = get_object_or_404(get_user_model(), username=payload.validated_data["username"])
        try:
            membership = add_member(organization=request.tenant, user=user, role=role)
        except MembershipError as exc:
            raise ValidationError({"username": [str(exc)]}) from exc
        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance: Membership) -> None:
        caller_role = get_request_role(self.request)
        if not role_at_least(caller_role, instance.role):
            raise PermissionDenied("You cannot remove a member with a higher role.")
        try:
            remove_member(membership=instance)
        except MembershipError as exc:
            raise ValidationError({"detail": str(exc)}) from exc


class ApiKeyViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    read_role = Role.ADMIN
    write_role = Role.ADMIN

    def get_queryset(self) -> QuerySet[ApiKey]:
        return ApiKey.objects.filter(revoked_at__isnull=True)

    def get_serializer_class(self) -> type[serializers.BaseSerializer]:
        return ApiKeyCreateSerializer if self.action == "create" else ApiKeySerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        payload = ApiKeyCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        created_by = request.user if isinstance(request.user, get_user_model()) else None
        api_key, raw_key = ApiKey.issue(
            name=payload.validated_data["name"],
            role=payload.validated_data["role"],
            created_by=created_by,
        )
        data = ApiKeySerializer(api_key).data
        data["key"] = raw_key  # returned once, never stored in clear text
        return Response(data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance: ApiKey) -> None:
        instance.revoked_at = timezone.now()
        instance.save(update_fields=["revoked_at"])
