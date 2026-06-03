from decimal import Decimal

from django.conf import settings
from django.db import models, transaction


class Order(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Abierta'
        SENT = 'sent', 'En cocina'
        PREPARING = 'preparing', 'Preparando'
        READY = 'ready', 'Lista'
        SERVED = 'served', 'Servida'
        PAID = 'paid', 'Pagada'
        CANCELLED = 'cancelled', 'Cancelada'

    restaurant = models.ForeignKey('restaurant.RestaurantAccount', on_delete=models.PROTECT, related_name='orders', blank=True, null=True)
    branch = models.ForeignKey('restaurant.Branch', on_delete=models.PROTECT, related_name='orders', blank=True, null=True)
    table = models.ForeignKey('restaurant.DiningTable', on_delete=models.PROTECT, related_name='orders')
    waiter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def recalculate(self):
        subtotal = sum((item.line_subtotal for item in self.items.all()), Decimal('0.00'))
        tax = sum((item.line_tax for item in self.items.all()), Decimal('0.00'))
        self.subtotal = subtotal
        self.tax = tax
        self.total = subtotal + tax - self.discount
        self.save(update_fields=['subtotal', 'tax', 'total'])

    @transaction.atomic
    def consume_inventory(self):
        from inventory.models import StockMovement

        for item in self.items.select_related('menu_item').prefetch_related('menu_item__recipe'):
            for recipe_item in item.menu_item.recipe.all():
                ingredient = recipe_item.ingredient
                quantity = recipe_item.quantity * item.quantity
                ingredient.current_stock -= quantity
                ingredient.save(update_fields=['current_stock'])
                StockMovement.objects.create(
                    ingredient=ingredient,
                    movement_type=StockMovement.Type.SALE,
                    quantity=quantity,
                    note=f'Consumo automático pedido #{self.id}',
                    created_by=self.waiter,
                )

    def __str__(self):
        return f'Pedido #{self.pk}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey('inventory.MenuItem', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    notes = models.CharField(max_length=255, blank=True)
    sent_to_kitchen = models.BooleanField(default=False)

    @property
    def line_subtotal(self):
        return self.unit_price * self.quantity

    @property
    def line_tax(self):
        return self.line_subtotal * (self.tax_rate / Decimal('100.00'))

    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.menu_item.price
        if not self.tax_rate:
            self.tax_rate = self.menu_item.tax_rate
        super().save(*args, **kwargs)
        self.order.recalculate()


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = 'cash', 'Efectivo'
        CARD = 'card', 'Tarjeta'
        TRANSFER = 'transfer', 'Transferencia'
        MIXED = 'mixed', 'Mixto'

    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name='payment')
    restaurant = models.ForeignKey('restaurant.RestaurantAccount', on_delete=models.PROTECT, related_name='payments', blank=True, null=True)
    branch = models.ForeignKey('restaurant.Branch', on_delete=models.PROTECT, related_name='payments', blank=True, null=True)
    method = models.CharField(max_length=20, choices=Method.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    received = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    change = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reference = models.CharField(max_length=80, blank=True)
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='payments')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.order_id:
            self.restaurant = self.order.restaurant
            self.branch = self.order.branch
        self.change = max(self.received - self.amount, Decimal('0.00'))
        super().save(*args, **kwargs)

# Create your models here.
