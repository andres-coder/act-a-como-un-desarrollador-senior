from decimal import Decimal
from datetime import datetime, time

from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Sum
from django.shortcuts import render
from django.utils import timezone

from inventory.models import Ingredient
from restaurant.models import DiningTable
from sales.models import Order, OrderItem, Payment


def money_value(value):
    if value is None:
        return 0

    if isinstance(value, Decimal):
        return float(value)

    return value


def day_range(day):
    start = timezone.make_aware(
        datetime.combine(day, time.min)
    )

    end = start + timezone.timedelta(days=1)

    return start, end


def filter_by_day(queryset, field_name, day):
    start, end = day_range(day)

    return queryset.filter(
        **{
            f'{field_name}__gte': start,
            f'{field_name}__lt': end
        }
    )


@login_required
def dashboard(request):

    today = timezone.localdate()
    week_start = today - timezone.timedelta(days=6)

    user = request.user

    # ======================
    # SUPERUSER
    # ======================

    if user.is_superuser:

        payments = Payment.objects.select_related(
            'order'
        )

        orders = Order.objects.select_related(
            'table',
            'waiter'
        )

    # ======================
    # ADMIN
    # ======================

    elif user.role == 'admin':

        payments = Payment.objects.filter(
            restaurant=user.restaurant
        ).select_related('order')

        orders = Order.objects.filter(
            restaurant=user.restaurant
        ).select_related(
            'table',
            'waiter'
        )

    # ======================
    # MANAGER
    # ======================

    elif user.role == 'manager':

        payments = Payment.objects.filter(
            order__branch=user.branch
        ).select_related('order')

        orders = Order.objects.filter(
            branch=user.branch
        ).select_related(
            'table',
            'waiter'
        )

    # ======================
    # CASHIER
    # ======================

    elif user.role == 'cashier':

        payments = Payment.objects.filter(
            cashier=user
        ).select_related('order')

        orders = Order.objects.filter(
            payment__cashier=user
        ).select_related(
            'table',
            'waiter'
        ).distinct()

    # ======================
    # WAITER
    # ======================

    elif user.role == 'waiter':

        payments = Payment.objects.filter(
            order__waiter=user
        ).select_related('order')

        orders = Order.objects.filter(
            waiter=user
        ).select_related(
            'table',
            'waiter'
        )

    # ======================
    # CHEF
    # ======================

    else:

        payments = Payment.objects.none()

        orders = Order.objects.filter(
            branch=user.branch
        ).select_related(
            'table',
            'waiter'
        )

    # ======================
    # DATOS GENERALES
    # ======================

    tables = DiningTable.objects.all()

    ingredients = Ingredient.objects.all()

    if not user.is_superuser:

        if user.role == 'admin':

            tables = tables.filter(
                zone__branch__restaurant=user.restaurant
            )

            ingredients = ingredients.filter(
                restaurant=user.restaurant
            )

        elif user.branch:

            tables = tables.filter(
                zone__branch=user.branch
            )

            ingredients = ingredients.filter(
                restaurant=user.restaurant
            )

    order_items = OrderItem.objects.select_related(
        'order',
        'menu_item'
    )

    if not user.is_superuser:

        if user.role == 'admin':

            order_items = order_items.filter(
                order__restaurant=user.restaurant
            )

        elif user.role == 'manager':

            order_items = order_items.filter(
                order__branch=user.branch
            )

        elif user.role == 'waiter':

            order_items = order_items.filter(
                order__waiter=user
            )

        elif user.role == 'cashier':

            order_items = order_items.filter(
                order__payment__cashier=user
            )

        else:

            order_items = order_items.none()

    total_sales = payments.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    total_payments = payments.count()

    payments_today = filter_by_day(
        payments,
        'created_at',
        today
    )

    open_orders = orders.exclude(
        status__in=[
            Order.Status.PAID,
            Order.Status.CANCELLED
        ]
    ).count()

    occupied_tables = tables.filter(
        status=DiningTable.Status.OCCUPIED
    ).count()

    low_stock = ingredients.filter(
        current_stock__lte=F('min_stock')
    ).count()

    paid_order_items = order_items.filter(
        order__status=Order.Status.PAID
    )

    products_sold = paid_order_items.aggregate(
        total=Sum('quantity')
    )['total'] or 0

    kitchen_orders = orders.filter(
        status__in=[
            Order.Status.SENT,
            Order.Status.PREPARING,
            Order.Status.READY
        ]
    ).count()

    average_ticket = Decimal('0.00')

    if total_payments:
        average_ticket = total_sales / total_payments

    daily_sales = []
    daily_labels = []

    for offset in range(7):

        day = week_start + timezone.timedelta(days=offset)

        daily_labels.append(
            day.strftime('%d/%m')
        )

        total = filter_by_day(
            payments,
            'created_at',
            day
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        daily_sales.append(
            money_value(total)
        )

    top_products = list(
        paid_order_items.values(
            'menu_item__name'
        ).annotate(
            total=Sum('quantity')
        ).order_by('-total')[:5]
    )

    payment_methods = list(
        payments.values('method').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('method')
    )

    order_statuses = list(
        orders.values('status').annotate(
            total=Count('id')
        ).order_by('status')
    )

    table_statuses = list(
        tables.values('status').annotate(
            total=Count('id')
        ).order_by('status')
    )

    status_labels = dict(Order.Status.choices)

    table_status_labels = dict(
        DiningTable.Status.choices
    )

    method_labels = dict(
        Payment.Method.choices
    )

    chart_data = {
        'dailySales': {
            'labels': daily_labels,
            'values': daily_sales,
        },

        'topProducts': {
            'labels': [
                row['menu_item__name'] or 'Sin nombre'
                for row in top_products
            ],
            'values': [
                row['total'] or 0
                for row in top_products
            ],
        },

        'paymentMethods': {
            'labels': [
                method_labels.get(
                    row['method'],
                    row['method']
                )
                for row in payment_methods
            ],

            'values': [
                money_value(row['total'])
                for row in payment_methods
            ],
        },

        'orderStatuses': {
            'labels': [
                status_labels.get(
                    row['status'],
                    row['status']
                )
                for row in order_statuses
            ],

            'values': [
                row['total']
                for row in order_statuses
            ],
        },

        'tableStatuses': {
            'labels': [
                table_status_labels.get(
                    row['status'],
                    row['status']
                )
                for row in table_statuses
            ],

            'values': [
                row['total']
                for row in table_statuses
            ],
        },
    }

    context = {
        'sales_today': total_sales,
        'open_orders': open_orders,
        'occupied_tables': occupied_tables,
        'low_stock': low_stock,
        'average_ticket': average_ticket,
        'total_payments': total_payments,
        'products_sold_today': products_sold,
        'kitchen_orders': kitchen_orders,
        'total_tables': tables.count(),
        'chart_data': chart_data,

        'low_stock_items': ingredients.filter(
            current_stock__lte=F('min_stock')
        )[:6],

        'recent_orders': orders.order_by(
            '-id'
        ).select_related(
            'table',
            'waiter'
        )[:8],
    }

    return render(
        request,
        'dashboard/index.html',
        context
    )