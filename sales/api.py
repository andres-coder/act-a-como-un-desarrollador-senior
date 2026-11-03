from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsPOSStaff
from kitchen.models import KitchenTicket
from restaurant.models import DiningTable
from sales.models import Order, OrderItem, Payment


class OrderItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(
        source='menu_item.name',
        read_only=True
    )

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'menu_item',
            'menu_item_name',
            'quantity',
            'unit_price',
            'tax_rate',
            'notes',
            'sent_to_kitchen'
        ]
        read_only_fields = [
            'unit_price',
            'tax_rate',
            'sent_to_kitchen'
        ]


class OrderSerializer(serializers.ModelSerializer):

    items = OrderItemSerializer(many=True)

    table_number = serializers.CharField(
        source='table.number',
        read_only=True
    )

    waiter_name = serializers.CharField(
        source='waiter.get_full_name',
        read_only=True
    )

    class Meta:
        model = Order

        fields = [
            'id',
            'table',
            'table_number',
            'waiter',
            'waiter_name',
            'status',
            'subtotal',
            'tax',
            'discount',
            'total',
            'notes',
            'created_at',
            'closed_at',
            'items'
        ]

        read_only_fields = [
            'waiter',
            'subtotal',
            'tax',
            'total',
            'created_at',
            'closed_at'
        ]

    def validate_table(self, value):

        if not value.is_active:
            raise serializers.ValidationError(
                'La mesa seleccionada no está disponible.'
            )

        return value

    def validate(self, attrs):

        print("\n========== VALIDANDO PEDIDO ==========")

        items = attrs.get('items', [])

        shortages = []

        for row in items:

            menu_item = row.get('menu_item')
            qty = row.get('quantity', 0)

            print(f"Producto: {menu_item}")
            print(f"Cantidad: {qty}")

            if not menu_item:
                print("NO HAY MENU ITEM")
                continue

            if hasattr(menu_item, 'recipe'):

                for recipe_item in menu_item.recipe.all():

                    ingredient = recipe_item.ingredient
                    required = recipe_item.quantity * qty

                    print(f"Ingrediente: {ingredient.name}")
                    print(f"Stock actual: {ingredient.current_stock}")
                    print(f"Necesario: {required}")

                    if ingredient.current_stock < required:

                        shortages.append(
                            f"{ingredient.name}: requiere "
                            f"{required} {ingredient.unit}, "
                            f"disponible {ingredient.current_stock}"
                        )

        if shortages:

            print("FALTANTES:")
            print(shortages)

            raise serializers.ValidationError({
                'items': shortages
            })

        print("VALIDACIÓN OK")

        return attrs

    def create(self, validated_data):

        items_data = validated_data.pop('items')

        user = self.context['request'].user

        table = validated_data.get('table')

        order = Order.objects.create(
            waiter=user,
            restaurant=(
                getattr(user, 'restaurant', None)
                or getattr(
                    getattr(table.zone, 'branch', None),
                    'restaurant',
                    None
                )
            ),
            branch=getattr(table.zone, 'branch', None),
            **validated_data,
        )

        for row in items_data:

            menu_item = row['menu_item']

            row.pop('unit_price', None)
            row.pop('tax_rate', None)

            OrderItem.objects.create(
                order=order,
                unit_price=menu_item.price,
                tax_rate=menu_item.tax_rate,
                **row
            )

        order.table.status = DiningTable.Status.OCCUPIED

        order.table.save(update_fields=['status'])

        order.recalculate()

        return order

    def update(self, instance, validated_data):

        items_data = validated_data.pop('items', None)

        new_table = validated_data.pop('table', None)

        old_table = instance.table

        old_status = instance.status

        if new_table and new_table != old_table:

            if instance.status in [
                Order.Status.PAID,
                Order.Status.CANCELLED
            ]:
                raise serializers.ValidationError(
                    'No se puede transferir un pedido cerrado.'
                )

            new_table.status = DiningTable.Status.OCCUPIED

            new_table.save(update_fields=['status'])

            other_open_orders = (
                old_table.orders
                .exclude(pk=instance.pk)
                .filter(
                    status__in=[
                        Order.Status.OPEN,
                        Order.Status.SENT,
                        Order.Status.PREPARING,
                        Order.Status.READY,
                        Order.Status.SERVED,
                    ]
                )
            )

            if not other_open_orders.exists():

                old_table.status = DiningTable.Status.AVAILABLE

                old_table.save(update_fields=['status'])

            instance.table = new_table

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()

        # Consumir inventario
        if (
            instance.status == Order.Status.PREPARING
            and old_status != Order.Status.PREPARING
        ):
            try:
                instance.consume_inventory()
            except Exception as e:
                print("ERROR INVENTARIO:", str(e))

        if items_data is not None:

            instance.items.all().delete()

            for row in items_data:

                menu_item = row['menu_item']

                row.pop('unit_price', None)
                row.pop('tax_rate', None)

                OrderItem.objects.create(
                    order=instance,
                    unit_price=menu_item.price,
                    tax_rate=menu_item.tax_rate,
                    **row
                )

        instance.recalculate()

        return instance


class PaymentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Payment
        fields = '__all__'

        read_only_fields = [
            'cashier',
            'change',
            'created_at'
        ]

    def validate(self, attrs):

        order = attrs['order']

        if hasattr(order, 'payment'):
            raise serializers.ValidationError(
                'Este pedido ya tiene un pago registrado.'
            )

        if order.status == Order.Status.CANCELLED:
            raise serializers.ValidationError(
                'No se puede cobrar un pedido cancelado.'
            )

        if attrs['amount'] <= 0:
            raise serializers.ValidationError(
                'El valor a pagar debe ser mayor que cero.'
            )

        return attrs

    def create(self, validated_data):

        payment = Payment.objects.create(
            cashier=self.context['request'].user,
            **validated_data
        )

        order = payment.order

        order.status = Order.Status.PAID
        order.closed_at = timezone.now()

        order.save(update_fields=['status', 'closed_at'])

        order.table.status = DiningTable.Status.CLEANING

        order.table.save(update_fields=['status'])

        return payment


class OrderViewSet(viewsets.ModelViewSet):

    queryset = (
        Order.objects
        .select_related('table', 'waiter')
        .prefetch_related('items__menu_item')
    )

    serializer_class = OrderSerializer

    permission_classes = [IsPOSStaff]

    def get_queryset(self):

        qs = super().get_queryset()

        user = self.request.user

        # SUPERUSER
        if user.is_superuser:
            return qs

        # ADMIN
        if user.role == 'admin':
            return qs.filter(
                restaurant=user.restaurant
            )

        # MANAGER
        if user.role == 'manager':
            return qs.filter(
                branch=user.branch
            )

        # WAITER
        if user.role == 'waiter':
            return qs.filter(
                waiter=user
            )

        # CASHIER
        if user.role == 'cashier':
            return qs.filter(
                payment__cashier=user
            ).distinct()

        return qs.none()

    @action(detail=True, methods=['post'])
    def send_to_kitchen(self, request, pk=None):

        order = self.get_object()

        order.status = Order.Status.SENT

        order.save(update_fields=['status'])

        order.items.update(sent_to_kitchen=True)

        KitchenTicket.objects.get_or_create(order=order)

        return Response({
            'status': order.status
        })


class PaymentViewSet(viewsets.ModelViewSet):

    queryset = (
        Payment.objects
        .select_related(
            'order',
            'cashier'
        )
    )

    serializer_class = PaymentSerializer

    permission_classes = [IsPOSStaff]

    def get_queryset(self):

        qs = super().get_queryset()

        user = self.request.user

        # SUPERUSER
        if user.is_superuser:
            return qs

        # ADMIN
        if user.role == 'admin':
            return qs.filter(
                restaurant=user.restaurant
            )

        # MANAGER
        if user.role == 'manager':
            return qs.filter(
                order__branch=user.branch
            )

        # CASHIER
        if user.role == 'cashier':
            return qs.filter(
                cashier=user
            )

        return qs.none()