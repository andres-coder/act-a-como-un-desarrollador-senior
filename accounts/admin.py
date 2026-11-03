from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import User


@admin.register(User)
class BembaUserAdmin(UserAdmin):

    list_display = (
        'username',
        'email',
        'restaurant',
        'branch',
        'role',
        'is_active_employee',
        'is_staff',
    )

    list_filter = (
        'restaurant',
        'branch',
        'role',
        'is_active_employee',
        'is_staff',
    )

    fieldsets = UserAdmin.fieldsets + (
        (
            'Bemba',
            {
                'fields': (
                    'restaurant',
                    'branch',
                    'role',
                    'phone',
                    'is_active_employee',
                )
            }
        ),
    )

    def get_queryset(self, request):

        queryset = super().get_queryset(request)

        # SUPERUSER
        if request.user.is_superuser:
            return queryset

        # Sin restaurante
        if not request.user.restaurant_id:
            return queryset.none()

        # ADMIN
        if request.user.role == 'admin':

            return queryset.filter(
                restaurant=request.user.restaurant
            ).exclude(
                is_superuser=True
            )

        # MANAGER
        if request.user.role == 'manager':

            return queryset.filter(
                branch=request.user.branch
            ).exclude(
                role='admin'
            ).exclude(
                is_superuser=True
            )

        return queryset.filter(
            pk=request.user.pk
        )

    def save_model(self, request, obj, form, change):

        if not request.user.is_superuser:

            obj.restaurant = request.user.restaurant

            # Manager no puede mover empleados a otra sucursal
            if request.user.role == 'manager':
                obj.branch = request.user.branch

        super().save_model(
            request,
            obj,
            form,
            change
        )

    def has_delete_permission(self, request, obj=None):

        if request.user.is_superuser:
            return True

        return request.user.role == 'admin'

    def has_change_permission(self, request, obj=None):

        if request.user.is_superuser:
            return True

        if obj is None:
            return True

        # Admin NO puede editar superusuarios
        if obj.is_superuser:
            return False

        # Manager NO puede editar admins
        if request.user.role == 'manager' and obj.role == 'admin':
            return False

        return True