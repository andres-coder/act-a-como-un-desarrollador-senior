from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsOrderOperator, IsPOSStaff
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
            'status',
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
        items = attrs.get('items', [])
        request = self.context['request']
        user = request.user
        if not user.is_superuser and user.role not in ['admin', 'manager', 'waiter']:
            raise serializers.ValidationError('Solo propietario, gerencia o mesero puede modificar pedidos.')
        table = attrs.get('table') or getattr(self.instance, 'table', None)
        table_branch = getattr(getattr(table, 'zone', None), 'branch', None)
        table_restaurant = getattr(table_branch, 'restaurant', None)

        if not table or not table_branch or not table_restaurant:
            raise serializers.ValidationError({'table': 'La mesa debe pertenecer a una sucursal válida.'})
        if not user.is_superuser:
            if not user.restaurant_id or user.restaurant_id != table_restaurant.id:
                raise serializers.ValidationError({'table': 'La mesa no pertenece a tu restaurante.'})
            if user.role in ['manager', 'cashier', 'waiter'] and (
                not user.branch_id or user.branch_id != table_branch.id
            ):
                raise serializers.ValidationError({'table': 'La mesa no pertenece a tu sucursal.'})
        shortages = []

        for row in items:
            menu_item = row.get('menu_item')
            qty = row.get('quantity', 0)
            if not menu_item:
                continue
            if not menu_item.is_available:
                raise serializers.ValidationError({'items': ['El producto no está disponible.']})
            if table_restaurant and menu_item.restaurant_id != table_restaurant.id:
                raise serializers.ValidationError(
                    {'items': ['Los productos deben pertenecer al restaurante de la mesa.']}
                )
            for recipe_item in menu_item.recipe.all():
                ingredient = recipe_item.ingredient
                required = recipe_item.quantity * qty
                if ingredient.current_stock < required:
                    shortages.append(
                        f"{ingredient.name}: requiere {required} {ingredient.unit}, "
                        f"disponible {ingredient.current_stock}"
                    )

        if shortages:
            raise serializers.ValidationError({'items': shortages})

        return attrs

    @transaction.atomic
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

    @transaction.atomic
    def update(self, instance, validated_data):

        instance = Order.objects.select_for_update().get(pk=instance.pk)

        if instance.status in [Order.Status.PAID, Order.Status.CANCELLED]:
            raise serializers.ValidationError('No se puede modificar un pedido cerrado.')

        items_data = validated_data.pop('items', None)

        new_table = validated_data.pop('table', None)

        old_table = instance.table

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
            'created_at',
            'restaurant',
            'branch',
        ]

    def validate(self, attrs):
        order = attrs['order']
        user = self.context['request'].user

        if Payment.objects.filter(order=order).exists():
            raise serializers.ValidationError(
                'Este pedido ya tiene un pago registrado.'
            )

        if order.status in [Order.Status.PAID, Order.Status.CANCELLED]:
            raise serializers.ValidationError(
                'No se puede cobrar un pedido cerrado o cancelado.'
            )

        if not user.has_role('admin', 'manager', 'cashier'):
            raise serializers.ValidationError('Solo caja, gerencia o administración puede registrar pagos.')

        if not user.is_superuser and (
            not user.restaurant_id or order.restaurant_id != user.restaurant_id
        ):
            raise serializers.ValidationError('El pedido no pertenece a tu restaurante.')

        if user.role in ['manager', 'cashier'] and (
            not user.branch_id or order.branch_id != user.branch_id
        ):
            raise serializers.ValidationError('El pedido no pertenece a tu sucursal.')

        if order.status not in [Order.Status.READY, Order.Status.SERVED]:
            raise serializers.ValidationError(
                {'order': 'Solo se pueden cobrar pedidos listos o servidos.'}
            )

        if attrs['amount'] != order.total:
            raise serializers.ValidationError({'amount': 'El pago debe coincidir con el total del pedido.'})

        if attrs['amount'] <= 0:
            raise serializers.ValidationError(
                'El valor a pagar debe ser mayor que cero.'
            )

        if attrs['method'] == Payment.Method.CASH and attrs.get('received', 0) < attrs['amount']:
            raise serializers.ValidationError({'received': 'El efectivo recibido no cubre el total del pedido.'})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        order = Order.objects.select_for_update().select_related('table').get(pk=validated_data['order'].pk)
        if Payment.objects.filter(order=order).exists():
            raise serializers.ValidationError('Este pedido ya tiene un pago registrado.')
        if order.status not in [Order.Status.READY, Order.Status.SERVED]:
            raise serializers.ValidationError({'order': 'El pedido ya no está listo para cobrar.'})
        if validated_data['amount'] != order.total:
            raise serializers.ValidationError({'amount': 'El total del pedido cambió; vuelve a cargar el cobro.'})
        user = self.context['request'].user
        if not user.is_superuser and (
            not user.restaurant_id or user.restaurant_id != order.restaurant_id
        ):
            raise serializers.ValidationError('El pedido no pertenece a tu restaurante.')
        if user.role in ['manager', 'cashier'] and (
            not user.branch_id or user.branch_id != order.branch_id
        ):
            raise serializers.ValidationError('El pedido no pertenece a tu sucursal.')
        payment = Payment.objects.create(
            cashier=user,
            order=order,
            restaurant=order.restaurant,
            branch=order.branch,
            method=validated_data['method'],
            amount=validated_data['amount'],
            received=validated_data.get('received', 0),
            reference=validated_data.get('reference', ''),
        )
        try:
            order.consume_inventory()
        except DjangoValidationError as error:
            raise serializers.ValidationError({'order': error.messages}) from error

        order.status = Order.Status.PAID
        order.closed_at = timezone.now()

        order.save(update_fields=['status', 'closed_at'])

        order.table.status = DiningTable.Status.CLEANING

        order.table.save(update_fields=['status'])

        KitchenTicket.objects.filter(order=order).update(status=KitchenTicket.Status.DELIVERED)

        return payment


class OrderViewSet(viewsets.ModelViewSet):

    queryset = (
        Order.objects
        .select_related('table', 'waiter')
        .prefetch_related('items__menu_item')
    )

    serializer_class = OrderSerializer

    permission_classes = [IsPOSStaff]

    def get_permissions(self):
        if self.action in {'create', 'update', 'partial_update', 'destroy', 'send_to_kitchen'}:
            return [IsOrderOperator()]
        return super().get_permissions()

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
            return qs.filter(branch=user.branch)

        return qs.none()

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def send_to_kitchen(self, request, pk=None):

        if not request.user.is_superuser and request.user.role not in ['admin', 'manager', 'waiter']:
            return Response({'detail': 'Solo propietario, gerencia o mesero puede enviar pedidos a cocina.'}, status=403)

        order = self.get_object()
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != Order.Status.OPEN:
            return Response({'detail': 'Solo se pueden enviar a cocina pedidos abiertos.'}, status=400)

        order.status = Order.Status.SENT

        order.save(update_fields=['status'])

        order.items.update(sent_to_kitchen=True)

        KitchenTicket.objects.get_or_create(order=order)

        return Response({
            'status': order.status
        })


class PaymentViewSet(viewsets.ModelViewSet):

    http_method_names = ['get', 'post', 'head', 'options']

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
