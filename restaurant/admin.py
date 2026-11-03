from django.contrib import admin

from .models import (
    SubscriptionPlan,
    RestaurantAccount,
    Branch,
    Zone,
    DiningTable
)


class TenantAdminMixin:
    """
    Filtra información por restaurante
    para usuarios no superadmin.
    """

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        if hasattr(request.user, 'restaurant'):
            restaurant = request.user.restaurant

            if hasattr(self.model, 'restaurant'):
                return qs.filter(restaurant=restaurant)

        return qs.none()


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'monthly_price',
        'max_branches',
        'max_users',
    )


@admin.register(RestaurantAccount)
class RestaurantAccountAdmin(admin.ModelAdmin):
    list_display = (
        'business_name',
        'email',
        'phone',
        'status',
    )

    fieldsets = (
        ('Información básica', {
            'fields': (
                'plan',
                'business_name',
                'legal_name',
                'status',
            )
        }),

        ('Branding', {
            'fields': (
                'logo',
                'primary_color',
            )
        }),

        ('Información fiscal', {
            'fields': (
                'nit',
                'address',
                'phone',
                'email',
                'website',
            )
        }),
    )


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'restaurant',
        'phone',
    )


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'branch',
    )


@admin.register(DiningTable)
class DiningTableAdmin(admin.ModelAdmin):
    list_display = (
        'number',
        'zone',
        'status',
    )