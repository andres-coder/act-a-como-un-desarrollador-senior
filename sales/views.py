from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from accounts.permissions import role_required
from inventory.models import Category, MenuItem
from restaurant.models import DiningTable
from restaurant.tenancy import scoped_queryset
from sales.models import Order, Payment


@login_required
@role_required('admin', 'manager', 'cashier', 'waiter')
def pos(request):
    tables = scoped_queryset(DiningTable.objects.filter(is_active=True), request.user, 'zone__branch__restaurant')
    categories = scoped_queryset(Category.objects.filter(is_active=True), request.user)
    items = scoped_queryset(MenuItem.objects.filter(is_available=True), request.user)
    open_orders = scoped_queryset(Order.objects.exclude(status__in=[Order.Status.PAID, Order.Status.CANCELLED]), request.user)
    return render(request, 'sales/pos.html', {
        'tables': tables.select_related('zone__branch'),
        'categories': categories,
        'items': items.select_related('category'),
        'open_orders': open_orders.select_related('table', 'waiter')[:12],
    })


@login_required
@role_required('admin', 'manager', 'cashier', 'waiter')
def ticket(request, pk):
    orders = scoped_queryset(Order.objects.select_related('table', 'waiter').prefetch_related('items__menu_item'), request.user)
    order = get_object_or_404(orders, pk=pk)
    return render(request, 'sales/ticket.html', {'order': order})


@login_required
@role_required('admin', 'manager', 'cashier', 'waiter')
def checkout(request, pk):
    orders = scoped_queryset(Order.objects.select_related('table', 'waiter').prefetch_related('items__menu_item'), request.user)
    order = get_object_or_404(orders, pk=pk)
    tables = scoped_queryset(DiningTable.objects.filter(is_active=True), request.user, 'zone__branch__restaurant')
    return render(request, 'sales/checkout.html', {
        'order': order,
        'payment_methods': Payment.Method.choices,
        'tables': tables.select_related('zone__branch'),
    })

# Create your views here.
