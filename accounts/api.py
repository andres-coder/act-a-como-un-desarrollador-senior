from django.contrib.auth import get_user_model
from rest_framework import serializers, viewsets

from accounts.permissions import IsAdminOrManager, has_valid_employee_scope


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'restaurant', 'branch', 'role', 'phone', 'is_active_employee', 'password']
        read_only_fields = ['restaurant', 'branch', 'is_active_employee']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_superuser:
            self.fields['restaurant'].read_only = False
            self.fields['branch'].read_only = False

    def validate(self, attrs):
        request_user = self.context['request'].user
        role = attrs.get('role', getattr(self.instance, 'role', User.Role.WAITER))
        if self.instance and self.instance.is_superuser:
            raise serializers.ValidationError('No se puede administrar el superadministrador desde este endpoint.')
        allowed_roles = {
            User.Role.ADMIN: {User.Role.MANAGER, User.Role.CASHIER, User.Role.WAITER, User.Role.CHEF},
            User.Role.MANAGER: {User.Role.CASHIER, User.Role.WAITER, User.Role.CHEF},
        }
        if not request_user.is_superuser and role not in allowed_roles.get(request_user.role, set()):
            raise serializers.ValidationError({'role': 'No tienes permiso para asignar este rol.'})
        if not request_user.is_superuser and not request_user.branch_id:
            raise serializers.ValidationError({'branch': 'Asigna una sucursal a tu perfil antes de crear empleados.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return super().get_queryset()
        if not has_valid_employee_scope(user):
            return super().get_queryset().none()
        queryset = super().get_queryset().exclude(is_superuser=True)
        if user.role == User.Role.ADMIN:
            return queryset.filter(restaurant=user.restaurant).exclude(role=User.Role.ADMIN)
        if user.role == User.Role.MANAGER:
            return queryset.filter(branch=user.branch).exclude(role__in=[User.Role.ADMIN, User.Role.MANAGER])
        return queryset.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            serializer.save()
            return
        serializer.save(restaurant=user.restaurant, branch=user.branch)
