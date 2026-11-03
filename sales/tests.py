from decimal import Decimal

from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import ValidationError

from accounts.models import User
from inventory.models import Category, Ingredient, MenuItem, RecipeItem, StockMovement
from restaurant.models import Branch, DiningTable, RestaurantAccount, SubscriptionPlan, Zone
from sales.api import OrderSerializer, PaymentSerializer
from sales.models import Order, OrderItem, Payment
from django.test import TestCase


class SalesFlowTests(TestCase):
    def setUp(self):
        self.plan = SubscriptionPlan.objects.create(name='QA', max_branches=2, max_users=10)
        self.restaurant = RestaurantAccount.objects.create(
            plan=self.plan,
            business_name='Restaurante QA',
            email='qa@example.com',
        )
        self.branch = Branch.objects.create(restaurant=self.restaurant, name='Principal')
        self.zone = Zone.objects.create(branch=self.branch, name='Salón')
        self.table = DiningTable.objects.create(zone=self.zone, number='1')
        self.waiter = self.make_user('waiter', User.Role.WAITER)
        self.cashier = self.make_user('cashier', User.Role.CASHIER)
        self.chef = self.make_user('chef', User.Role.CHEF)
        self.ingredient = Ingredient.objects.create(
            restaurant=self.restaurant,
            name='Arroz',
            unit=Ingredient.Unit.KG,
            current_stock=Decimal('5.000'),
            min_stock=Decimal('1.000'),
            unit_cost=Decimal('3000.00'),
        )
        category = Category.objects.create(restaurant=self.restaurant, name='Platos')
        self.menu_item = MenuItem.objects.create(
            restaurant=self.restaurant,
            category=category,
            name='Arroz con pollo',
            price=Decimal('15000.00'),
        )
        RecipeItem.objects.create(
            menu_item=self.menu_item,
            ingredient=self.ingredient,
            quantity=Decimal('0.500'),
        )
        self.factory = APIRequestFactory()

    def make_user(self, username, role):
        return User.objects.create_user(
            username=username,
            password='strong-password-123',
            role=role,
            restaurant=self.restaurant,
            branch=self.branch,
        )

    def create_order(self, status=Order.Status.OPEN):
        order = Order.objects.create(
            restaurant=self.restaurant,
            branch=self.branch,
            table=self.table,
            waiter=self.waiter,
            status=status,
        )
        OrderItem.objects.create(
            order=order,
            menu_item=self.menu_item,
            quantity=2,
            unit_price=self.menu_item.price,
            tax_rate=Decimal('0.00'),
        )
        order.refresh_from_db()
        return order

    def payment_serializer(self, user, data):
        request = self.factory.post('/api/payments/')
        request.user = user
        return PaymentSerializer(data=data, context={'request': request})

    def test_payment_closes_order_and_consumes_inventory_once(self):
        order = self.create_order(status=Order.Status.READY)
        serializer = self.payment_serializer(
            self.cashier,
            {
                'order': order.id,
                'method': 'cash',
                'amount': '30000.00',
                'received': '30000.00',
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        order.refresh_from_db()
        self.table.refresh_from_db()
        self.ingredient.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertIsNotNone(order.closed_at)
        self.assertIsNotNone(order.inventory_consumed_at)
        self.assertEqual(self.table.status, DiningTable.Status.CLEANING)
        self.assertEqual(self.ingredient.current_stock, Decimal('4.000'))
        self.assertEqual(StockMovement.objects.filter(ingredient=self.ingredient).count(), 1)
        self.assertFalse(order.consume_inventory())
        self.assertEqual(StockMovement.objects.filter(ingredient=self.ingredient).count(), 1)

    def test_payment_requires_exact_order_total(self):
        order = self.create_order(status=Order.Status.READY)
        serializer = self.payment_serializer(
            self.cashier,
            {'order': order.id, 'method': 'cash', 'amount': '1.00', 'received': '1.00'},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('amount', serializer.errors)

    def test_payment_requires_ready_or_served_order(self):
        order = self.create_order(status=Order.Status.OPEN)
        serializer = self.payment_serializer(
            self.cashier,
            {'order': order.id, 'method': 'cash', 'amount': '30000.00', 'received': '30000.00'},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('order', serializer.errors)

    def test_insufficient_inventory_rolls_back_payment_and_order(self):
        order = self.create_order(status=Order.Status.READY)
        self.ingredient.current_stock = Decimal('0.500')
        self.ingredient.save(update_fields=['current_stock'])
        serializer = self.payment_serializer(
            self.cashier,
            {'order': order.id, 'method': 'cash', 'amount': '30000.00', 'received': '30000.00'},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with self.assertRaises(ValidationError):
            serializer.save()

        order.refresh_from_db()
        self.ingredient.refresh_from_db()
        self.assertFalse(Payment.objects.filter(order=order).exists())
        self.assertEqual(order.status, Order.Status.READY)
        self.assertEqual(self.ingredient.current_stock, Decimal('0.500'))
        self.assertEqual(StockMovement.objects.filter(ingredient=self.ingredient).count(), 0)

    def test_waiter_cannot_register_payment(self):
        order = self.create_order()
        serializer = self.payment_serializer(
            self.waiter,
            {'order': order.id, 'method': 'cash', 'amount': '30000.00', 'received': '30000.00'},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)

    def test_order_cannot_use_table_from_another_restaurant(self):
        other_restaurant = RestaurantAccount.objects.create(
            plan=self.plan,
            business_name='Otro restaurante',
            email='other@example.com',
        )
        other_branch = Branch.objects.create(restaurant=other_restaurant, name='Otra sede')
        other_zone = Zone.objects.create(branch=other_branch, name='Otro salón')
        other_table = DiningTable.objects.create(zone=other_zone, number='99')
        other_category = Category.objects.create(restaurant=other_restaurant, name='Otros')
        other_item = MenuItem.objects.create(
            restaurant=other_restaurant,
            category=other_category,
            name='Producto ajeno',
            price=Decimal('10000.00'),
        )
        request = self.factory.post('/api/orders/')
        request.user = self.waiter
        serializer = OrderSerializer(
            data={'table': other_table.id, 'items': [{'menu_item': other_item.id, 'quantity': 1}]},
            context={'request': request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('table', serializer.errors)
