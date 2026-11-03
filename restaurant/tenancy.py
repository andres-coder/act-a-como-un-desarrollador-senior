from django.db.models import QuerySet


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

    # =========================
    # ADMIN → TODO restaurante
    # =========================
    if user.role == 'admin':
        return queryset.filter(**{
            restaurant_field: user.restaurant
        })

    # =========================
    # MANAGER → SU sucursal
    # =========================
    if user.role == 'manager':

        try:
            branch_field = restaurant_field.replace(
                'restaurant',
                'branch'
            )

            return queryset.filter(**{
                branch_field: user.branch
            })

        except Exception:
            return queryset.filter(**{
                restaurant_field: user.restaurant
            })

    # =========================
    # WAITER
    # =========================
    if user.role == 'waiter':

        # pedidos propios
        if queryset.model.__name__ == 'Order':
            return queryset.filter(waiter=user)

        return queryset.filter(**{
            restaurant_field: user.restaurant
        })

    # =========================
    # CASHIER
    # =========================
    if user.role == 'cashier':

        if queryset.model.__name__ == 'Payment':
            return queryset.filter(cashier=user)

        return queryset.filter(**{
            restaurant_field: user.restaurant
        })

    # =========================
    # CHEF
    # =========================
    if user.role == 'chef':
        return queryset.filter(**{
            restaurant_field: user.restaurant
        })

    return queryset.none()