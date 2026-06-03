from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db import models

from accounts.permissions import role_required
from inventory.forms import PurchaseOrderForm, SupplierForm
from inventory.models import (
    Ingredient,
    MenuItem,
    StockMovement,
    StockAlert,
    Supplier,
    PurchaseOrder,
    PurchaseOrderItem,
)
from restaurant.tenancy import scoped_queryset


@login_required
@role_required('admin', 'manager')
def inventory(request):
    ingredients = scoped_queryset(Ingredient.objects.all(), request.user)
    menu_items = scoped_queryset(MenuItem.objects.all(), request.user)
    movements = scoped_queryset(StockMovement.objects.all(), request.user)
    sale_movements = scoped_queryset(StockMovement.objects.filter(movement_type=StockMovement.Type.SALE), request.user)
    alerts = scoped_queryset(StockAlert.objects.filter(resolved=False), request.user).select_related('ingredient')
    low_stock_items = ingredients.filter(current_stock__lte=models.F('min_stock'))
    return render(request, 'inventory/index.html', {
        'ingredients': ingredients,
        'menu_items': menu_items.select_related('category'),
        'movements': movements.select_related('ingredient', 'created_by')[:10],
        'sale_movements_count': sale_movements.count(),
        'alerts': alerts,
        'low_stock_items': low_stock_items,
    })


@login_required
@role_required('admin', 'manager')
def alerts(request):
    alerts_qs = scoped_queryset(StockAlert.objects.filter(resolved=False).select_related('ingredient'), request.user)
    return render(request, 'inventory/alerts.html', {
        'alerts': alerts_qs,
    })


@login_required
@role_required('admin', 'manager')
@require_POST
def alert_action(request):
    action = request.POST.get('action')
    alert_id = request.POST.get('alert_id')
    alert = get_object_or_404(StockAlert, pk=alert_id)

    if action == 'resolve':
        alert.resolved = True
        alert.save(update_fields=['resolved'])
        return JsonResponse({'ok': True, 'resolved': True})

    if action == 'create_po':
        quantity = request.POST.get('quantity')
        item_quantity = float(quantity) if quantity else 0
        supplier_id = request.POST.get('supplier_id')
        supplier = get_object_or_404(Supplier, pk=supplier_id)

        po = PurchaseOrder.objects.create(
            restaurant=alert.restaurant,
            supplier=supplier,
            branch=alert.ingredient.restaurant.branch_set.filter(restaurant=alert.restaurant).first() if alert.ingredient.restaurant else None,
            created_by=request.user,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            ingredient=alert.ingredient,
            quantity=item_quantity,
            unit_cost=0,
        )
        po.update_total()
        return JsonResponse({'ok': True, 'purchase_order_id': po.id})

    return JsonResponse({'ok': False, 'error': 'Acción desconocida'}, status=400)


@login_required
@role_required('admin', 'manager')
def suppliers(request):
    suppliers_qs = scoped_queryset(Supplier.objects.all(), request.user)
    form = SupplierForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        supplier = form.save(commit=False)
        supplier.restaurant = getattr(request.user, 'restaurant', None)
        supplier.save()
        return HttpResponseRedirect(reverse('inventory_suppliers'))

    return render(request, 'inventory/suppliers.html', {
        'suppliers': suppliers_qs,
        'form': form,
    })


@login_required
@role_required('admin', 'manager')
def purchase_orders(request):
    orders = scoped_queryset(PurchaseOrder.objects.select_related('supplier', 'branch'), request.user)
    return render(request, 'inventory/purchase_orders.html', {
        'orders': orders,
    })


@login_required
@role_required('admin', 'manager')
def purchase_order_create(request):
    form = PurchaseOrderForm(request.POST or None)
    ingredients = scoped_queryset(Ingredient.objects.all(), request.user)
    if request.method == 'POST' and form.is_valid():
        supplier = form.cleaned_data['supplier']
        branch = form.cleaned_data['branch']
        notes = form.cleaned_data['notes']
        ingredient_id = request.POST.get('ingredient')
        quantity = request.POST.get('quantity')
        unit_cost = request.POST.get('unit_cost')
        ingredient = get_object_or_404(Ingredient, pk=ingredient_id)

        po = PurchaseOrder.objects.create(
            restaurant=supplier.restaurant or getattr(request.user, 'restaurant', None),
            supplier=supplier,
            branch=branch,
            notes=notes,
            created_by=request.user,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            ingredient=ingredient,
            quantity=quantity,
            unit_cost=unit_cost,
        )
        po.update_total()
        return HttpResponseRedirect(reverse('inventory_purchase_order_detail', args=[po.id]))

    return render(request, 'inventory/purchase_order_form.html', {
        'form': form,
        'ingredients': ingredients,
    })


@login_required
@role_required('admin', 'manager')
def purchase_order_detail(request, pk):
    po = get_object_or_404(scoped_queryset(PurchaseOrder.objects.all(), request.user), pk=pk)
    return render(request, 'inventory/purchase_order_detail.html', {
        'po': po,
    })


@login_required
@role_required('admin', 'manager')
@require_POST
def receive_purchase_order(request, pk):
    po = get_object_or_404(scoped_queryset(PurchaseOrder.objects.all(), request.user), pk=pk, status=PurchaseOrder.Status.OPEN)
    po.receive()
    return HttpResponseRedirect(reverse('inventory_purchase_order_detail', args=[po.id]))
