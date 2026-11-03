from django.db.models import QuerySet
from django.core.exceptions import FieldError


def scoped_queryset(
    queryset: QuerySet,
    user,
    restaurant_field='restaurant'
):
    """
    Filtra automáticamente por restaurante/sucursal
    según el rol del usuario.
    """

    # SUPERADMIN
    if user.is_superuser:
        return queryset

    # Sin restaurante → sin acceso
    if not getattr(user, 'restaurant', None):
        return queryset.none()

    if queryset.model.__name__ == 'RestaurantAccount':
        return queryset.filter(pk=user.restaurant_id)

    if queryset.model.__name__ == 'Branch' and user.role in ['manager', 'cashier', 'waiter', 'chef']:
        return queryset.filter(pk=user.branch_id) if user.branch_id else queryset.none()

    # =========================
    # ADMIN → TODO restaurante
    # =========================
    if user.role == 'admin':
        if queryset.model.__name__ == 'RestaurantAccount':
            return queryset.filter(pk=user.restaurant_id)
        return queryset.filter(**{
            restaurant_field: user.restaurant
        })

    # =========================
    # MANAGER → SU sucursal
    # =========================
    if user.role == 'manager':

        if not user.branch_id or user.branch.restaurant_id != user.restaurant_id:
            return queryset.none()
        if queryset.model.__name__ == 'Branch':
            return queryset.filter(pk=user.branch_id)

        try:
            if restaurant_field == 'restaurant':
                branch_field = 'branch'
            elif restaurant_field.endswith('__restaurant'):
                branch_field = restaurant_field[:-len('__restaurant')]
            else:
                branch_field = restaurant_field.replace('restaurant', 'branch')

            return queryset.filter(**{
                branch_field: user.branch
            })

        except FieldError:
            return queryset.filter(**{
                restaurant_field: user.restaurant
            })

    # =========================
    # WAITER
    # =========================
    if user.role == 'waiter':

        if queryset.model.__name__ == 'RestaurantAccount':
            return queryset.filter(pk=user.restaurant_id)
        if queryset.model.__name__ == 'Zone':
            return queryset.filter(branch=user.branch)

        # pedidos propios
        if queryset.model.__name__ == 'Order':
            return queryset.filter(waiter=user)

        if queryset.model.__name__ == 'DiningTable':
            if not user.branch_id:
                return queryset.none()
            return queryset.filter(zone__branch=user.branch)

        return queryset.filter(**{
            restaurant_field: user.restaurant
        })

    # =========================
    # CASHIER
    # =========================
    if user.role == 'cashier':

        if queryset.model.__name__ == 'RestaurantAccount':
            return queryset.none()

        if queryset.model.__name__ == 'Payment':
            return queryset.filter(cashier=user)

        if queryset.model.__name__ == 'Order':
            if not user.branch_id:
                return queryset.none()
            return queryset.filter(branch=user.branch)
        if queryset.model.__name__ == 'Zone':
            return queryset.filter(branch=user.branch)
        if queryset.model.__name__ == 'DiningTable':
            return queryset.filter(zone__branch=user.branch)

        return queryset.filter(**{
            restaurant_field: user.restaurant
        })

    # =========================
    # CHEF
    # =========================
    if user.role == 'chef':
        if queryset.model.__name__ == 'KitchenTicket':
            if not user.branch_id:
                return queryset.none()
            return queryset.filter(order__branch=user.branch)
        return queryset.none()

    return queryset.none()
