from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from accounts.permissions import role_required
from kitchen.models import KitchenTicket
from restaurant.tenancy import scoped_queryset
from sales.models import Order


@login_required
@role_required('admin', 'manager', 'chef')
def kitchen_board(request):
    tickets = scoped_queryset(
        KitchenTicket.objects.select_related('order__table').prefetch_related('order__items__menu_item'),
        request.user,
        'order__restaurant'
    )
    return render(request, 'kitchen/board.html', {'tickets': tickets})


@login_required
@role_required('admin', 'manager', 'chef')
@require_POST
@transaction.atomic
def update_ticket_status(request, order_id):
    new_status = request.POST.get('status')

    allowed_statuses = {'preparing', 'ready'}
    if new_status not in allowed_statuses:
        return JsonResponse(
            {'ok': False, 'message': 'Estado inválido.'},
            status=400
        )

    ticket = get_object_or_404(
        scoped_queryset(
            KitchenTicket.objects.select_related('order'),
            request.user,
            'order__restaurant'
        ),
        order_id=order_id
    )

    order = Order.objects.select_for_update().get(pk=ticket.order_id)

    transitions = {
        'sent': 'preparing',
        'preparing': 'ready',
    }

    if transitions.get(order.status) != new_status:
        return JsonResponse(
            {'ok': False, 'message': 'Transición no permitida.'},
            status=400
        )

    order.status = new_status
    order.save(update_fields=['status'])
    ticket.status = new_status
    ticket.save(update_fields=['status'])

    return JsonResponse({
        'ok': True,
        'status': order.status,
        'status_display': order.get_status_display(),
    })
