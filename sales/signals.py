from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from sales.models import Order, Payment
from inventory.models import StockMovement, StockAlert


@receiver(post_save, sender=Payment)
def consume_inventory_on_payment(sender, instance, created, **kwargs):
    """
    Descuenta automáticamente el inventario cuando se registra un pago.
    Crea movimientos de stock y alertas si hay stock bajo.
    """
    if not created:
        return
    
    order = instance.order
    
    # Verificar si ya se ha consumido el inventario (evitar duplicados)
    existing_movements = StockMovement.objects.filter(
        note__icontains=f'Consumo automático pedido #{order.id}'
    ).exists()
    
    if existing_movements:
        return  # Ya se ha descontado, no hacer nada
    
    try:
        order.consume_inventory()
        
        # Crear alertas para ingredientes con stock bajo
        for item in order.items.all():
            for recipe_item in item.menu_item.recipe.all():
                ingredient = recipe_item.ingredient
                if ingredient.current_stock <= ingredient.min_stock:
                    alert, created_alert = StockAlert.objects.get_or_create(
                        ingredient=ingredient,
                        resolved=False,
                        defaults={
                            'restaurant': ingredient.restaurant,
                            'message': f'Stock bajo: {ingredient.current_stock} {ingredient.unit} (mínimo: {ingredient.min_stock})',
                            'created_by': order.waiter,
                        }
                    )
                    if created_alert:
                        alert.notify()
    except Exception as e:
        print(f'Error al descontar inventario: {e}')


@receiver(post_save, sender=Order)
def notify_when_preparing(sender, instance, created, update_fields, **kwargs):
    """
    Descuenta el inventario cuando la orden cambia a estado PREPARING
    (para órdenes que no van por el flujo de pago).
    """
    if created or update_fields is None:
        return
    
    if 'status' in update_fields and instance.status == Order.Status.PREPARING:
        # Verificar si ya se ha consumido el inventario
        existing_movements = StockMovement.objects.filter(
            note__icontains=f'Consumo automático pedido #{instance.id}'
        ).exists()
        
        if existing_movements:
            return  # Ya se ha descontado, no hacer nada
        
        try:
            instance.consume_inventory()
        except Exception as e:
            print(f'Error al descontar inventario en PREPARING: {e}')

