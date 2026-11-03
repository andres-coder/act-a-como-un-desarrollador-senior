from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from restaurant.models import Branch, DiningTable, RestaurantAccount, SubscriptionPlan, Zone
from sales.models import Order, Payment


class SalesReportTests(TestCase):
    def setUp(self):
        plan = SubscriptionPlan.objects.create(name='Reports QA')
        self.restaurant = RestaurantAccount.objects.create(
            plan=plan, business_name='Reportes QA', email='reports@example.com',
        )
        branch = Branch.objects.create(restaurant=self.restaurant, name='Principal')
        zone = Zone.objects.create(branch=branch, name='Salón')
        table = DiningTable.objects.create(zone=zone, number='1')
        self.admin = User.objects.create_user(
            username='reports-admin', password='strong-password-123',
            role=User.Role.ADMIN, restaurant=self.restaurant, branch=branch,
        )
        self.other_restaurant = RestaurantAccount.objects.create(
            plan=plan, business_name='Otro local', email='other-reports@example.com',
        )
        self.create_paid_order(table, self.restaurant, branch, '15000.00')
        other_branch = Branch.objects.create(restaurant=self.other_restaurant, name='Otra sede')
        other_zone = Zone.objects.create(branch=other_branch, name='Otro salón')
        other_table = DiningTable.objects.create(zone=other_zone, number='2')
        self.create_paid_order(other_table, self.other_restaurant, other_branch, '90000.00')

    def create_paid_order(self, table, restaurant, branch, amount):
        cashier = User.objects.create_user(
            username=f'cashier-{restaurant.pk}', password='strong-password-123',
            role=User.Role.CASHIER, restaurant=restaurant, branch=branch,
        )
        order = Order.objects.create(
            restaurant=restaurant, branch=branch, table=table, waiter=cashier,
            status=Order.Status.PAID, total=Decimal(amount),
        )
        Payment.objects.create(
            order=order, method=Payment.Method.CARD, amount=Decimal(amount),
            cashier=cashier,
        )

    def test_report_scopes_payments_to_users_restaurant(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('reports'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['transactions'], 1)
        self.assertEqual(response.context['total'], Decimal('15000.00'))

    def test_sales_pdf_is_generated_for_authorized_user(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('sales_pdf'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF'))
