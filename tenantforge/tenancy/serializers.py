from __future__ import annotations

from rest_framework import serializers

from .models import ApiKey, Membership, Organization, Role


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "plan", "created_at"]
        read_only_fields = ["id", "plan", "created_at"]


class MembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "username", "role", "created_at"]
        read_only_fields = fields


class MembershipCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=Role.choices, default=Role.MEMBER)


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = ["id", "name", "prefix", "role", "created_at", "last_used_at"]
        read_only_fields = fields


class ApiKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    role = serializers.ChoiceField(choices=ApiKey.ROLE_CHOICES, default=Role.MEMBER)
