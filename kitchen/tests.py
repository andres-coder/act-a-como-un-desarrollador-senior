from decimal import Decimal

from django.urls import reverse
from accounts.models import User
from inventory.models import Category, Ingredient, MenuItem, RecipeItem
from kitchen.models import KitchenTicket
from restaurant.models import Branch, DiningTable, RestaurantAccount, SubscriptionPlan, Zone
from sales.models import Order, OrderItem
from django.test import TestCase


class KitchenFlowTests(TestCase):
    def setUp(self):
        plan = SubscriptionPlan.objects.create(name='Kitchen QA')
        self.restaurant = RestaurantAccount.objects.create(
            plan=plan,
            business_name='Cocina QA',
            email='kitchen@example.com',
        )
        self.branch = Branch.objects.create(restaurant=self.restaurant, name='Principal')
        zone = Zone.objects.create(branch=self.branch, name='Salón')
        table = DiningTable.objects.create(zone=zone, number='1')
        self.waiter = User.objects.create_user(
            username='kitchen-waiter', password='strong-password-123',
            role=User.Role.WAITER, restaurant=self.restaurant, branch=self.branch,
        )
        self.chef = User.objects.create_user(
            username='kitchen-chef', password='strong-password-123',
            role=User.Role.CHEF, restaurant=self.restaurant, branch=self.branch,
        )
        ingredient = Ingredient.objects.create(
            restaurant=self.restaurant, name='Ingrediente', unit=Ingredient.Unit.UNIT,
            current_stock=Decimal('10.000'), min_stock=Decimal('1.000'),
        )
        category = Category.objects.create(restaurant=self.restaurant, name='Platos')
        item = MenuItem.objects.create(
            restaurant=self.restaurant, category=category, name='Plato', price=Decimal('10000.00'),
        )
        RecipeItem.objects.create(menu_item=item, ingredient=ingredient, quantity=Decimal('1.000'))
        self.order = Order.objects.create(
            restaurant=self.restaurant, branch=self.branch, table=table,
            waiter=self.waiter, status=Order.Status.SENT,
        )
        OrderItem.objects.create(order=self.order, menu_item=item, quantity=1, unit_price=item.price)
        self.ticket = KitchenTicket.objects.create(order=self.order)

    def test_chef_updates_order_and_ticket_status(self):
        self.client.force_login(self.chef)

        response = self.client.post(reverse('kitchen_update_status', args=[self.order.id]), {'status': 'preparing'})

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PREPARING)
        self.assertEqual(self.ticket.status, KitchenTicket.Status.PREPARING)

    def test_chef_sees_only_tickets_from_assigned_branch(self):
        other_branch = Branch.objects.create(restaurant=self.restaurant, name='Otra sucursal')
        other_zone = Zone.objects.create(branch=other_branch, name='Otro salón')
        other_table = DiningTable.objects.create(zone=other_zone, number='2')
        other_waiter = User.objects.create_user(
            username='other-branch-waiter', password='strong-password-123',
            role=User.Role.WAITER, restaurant=self.restaurant, branch=other_branch,
        )
        other_order = Order.objects.create(
            restaurant=self.restaurant, branch=other_branch, table=other_table,
            waiter=other_waiter, status=Order.Status.SENT,
        )
        KitchenTicket.objects.create(order=other_order)

        self.client.force_login(self.chef)
        response = self.client.get(reverse('kitchen'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['tickets'].values_list('order_id', flat=True)), [self.order.id])
