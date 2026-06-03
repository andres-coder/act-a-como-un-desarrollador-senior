from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.permissions import role_required
from restaurant.models import DiningTable, Zone
from restaurant.tenancy import scoped_queryset
from sales.models import Order


@login_required
@role_required('admin', 'manager', 'cashier', 'waiter')
def tables(request):
    zones = scoped_queryset(Zone.objects.all(), request.user, 'branch__restaurant')
    tables_qs = scoped_queryset(DiningTable.objects.all(), request.user, 'zone__branch__restaurant')
    open_orders = scoped_queryset(
        Order.objects.exclude(status__in=[Order.Status.PAID, Order.Status.CANCELLED]),
        request.user,
    ).select_related('table')

    orders_by_table = {order.table_id: order for order in open_orders}
    for table in tables_qs:
        table.open_order = orders_by_table.get(table.id)

    return render(request, 'restaurant/tables.html', {
        'zones': zones.prefetch_related('tables'),
        'tables': tables_qs.select_related('zone'),
    })

# Create your views here.
