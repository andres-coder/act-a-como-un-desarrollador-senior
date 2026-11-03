from functools import wraps

from django.shortcuts import render
from rest_framework.permissions import BasePermission


ROLE_HOME_NAMES = {
    'admin': 'dashboard',
    'manager': 'dashboard',
    'cashier': 'pos',
    'waiter': 'tables',
    'chef': 'kitchen',
}


def has_valid_employee_scope(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not user.is_active_employee or not user.restaurant_id:
        return False
    if user.role == 'admin':
        return not user.branch_id or user.branch.restaurant_id == user.restaurant_id
    return bool(
        user.branch_id
        and user.branch.restaurant_id == user.restaurant_id
        and user.role in ROLE_HOME_NAMES
    )


def role_home_name(user):
    if user.is_superuser:
        return 'admin:index'
    return ROLE_HOME_NAMES.get(user.role, 'dashboard')


class RolePermission(BasePermission):
    allowed_roles = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and has_valid_employee_scope(user)
            and (user.is_superuser or user.role in self.allowed_roles)
        )


class IsAdminOrManager(RolePermission):
    allowed_roles = ('admin', 'manager')


class IsPOSStaff(RolePermission):
    allowed_roles = ('admin', 'manager', 'cashier', 'waiter')


class IsOrderOperator(RolePermission):
    allowed_roles = ('admin', 'manager', 'waiter')


class IsKitchenStaff(RolePermission):
    allowed_roles = ('admin', 'manager', 'chef')


class IsSystemAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class IsTenantOwnerReadOnly(RolePermission):
    allowed_roles = ('admin', 'manager')

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.method in ('GET', 'HEAD', 'OPTIONS') or request.user.is_superuser


class IsBranchStaffReadOnly(RolePermission):
    allowed_roles = ('admin', 'manager', 'cashier', 'waiter')

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.method in ('GET', 'HEAD', 'OPTIONS') or request.user.is_superuser or request.user.role in ('admin', 'manager')


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if (
                has_valid_employee_scope(request.user)
                and (request.user.is_superuser or request.user.role in roles)
            ):
                return view_func(request, *args, **kwargs)
            return render(request, 'error.html', {
                'message': 'No tienes permiso para acceder aquí.'
            }, status=403)
        return _wrapped
    return decorator
