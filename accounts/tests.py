from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from restaurant.models import Branch, DiningTable, RestaurantAccount, SubscriptionPlan, Zone


class AuthenticationAndRoleTests(TestCase):
    def setUp(self):
        plan = SubscriptionPlan.objects.create(name='Accounts QA')
        self.restaurant = RestaurantAccount.objects.create(plan=plan, business_name='Accounts QA')
        self.branch = Branch.objects.create(restaurant=self.restaurant, name='Principal')
        zone = Zone.objects.create(branch=self.branch, name='Salón')
        DiningTable.objects.create(zone=zone, number='1')
        self.cashier = User.objects.create_user(
            username='accounts-cashier', password='strong-password-123',
            role=User.Role.CASHIER, restaurant=self.restaurant, branch=self.branch,
        )
        self.waiter = User.objects.create_user(
            username='accounts-waiter', password='strong-password-123',
            role=User.Role.WAITER, restaurant=self.restaurant, branch=self.branch,
        )
        self.chef = User.objects.create_user(
            username='accounts-chef', password='strong-password-123',
            role=User.Role.CHEF, restaurant=self.restaurant, branch=self.branch,
        )
        self.manager = User.objects.create_user(
            username='accounts-manager', password='strong-password-123',
            role=User.Role.MANAGER, restaurant=self.restaurant, branch=self.branch,
        )
        self.owner = User.objects.create_user(
            username='accounts-owner', password='strong-password-123',
            role=User.Role.ADMIN, restaurant=self.restaurant,
        )
        self.client = APIClient()

    def test_api_rejects_unauthenticated_request(self):
        response = self.client.get('/api/orders/')
        self.assertEqual(response.status_code, 401)

    def test_jwt_authenticates_user_and_role_limits_user_management(self):
        response = self.client.post(
            '/api/auth/token/',
            {'username': self.cashier.username, 'password': 'strong-password-123'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        denied = self.client.get('/api/users/')
        self.assertEqual(denied.status_code, 403)

    def test_profiles_land_in_their_own_work_area(self):
        role_destinations = [
            (self.cashier, 'pos'),
            (self.waiter, 'tables'),
            (self.chef, 'kitchen'),
        ]
        for user, destination in role_destinations:
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse('dashboard'))
                self.assertRedirects(response, reverse(destination), fetch_redirect_response=False)

        for user, expected_heading in [
            (self.owner, 'Panel del propietario'),
            (self.manager, 'Panel de gerencia'),
        ]:
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse('dashboard'))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['dashboard_title'], expected_heading)

    def test_login_redirects_users_to_their_role_home(self):
        client = APIClient()
        response = client.post(reverse('login'), {
            'username': self.chef.username,
            'password': 'strong-password-123',
        })
        self.assertRedirects(response, reverse('kitchen'), fetch_redirect_response=False)

        system_admin = User.objects.create_superuser(
            username='system-admin', email='system@example.com', password='strong-password-123',
        )
        response = client.post(reverse('login'), {
            'username': system_admin.username,
            'password': 'strong-password-123',
        })
        self.assertRedirects(response, reverse('admin:index'), fetch_redirect_response=False)

    def test_cashier_and_chef_do_not_receive_management_views(self):
        self.client.force_login(self.cashier)
        cashier_pos = self.client.get(reverse('pos'))
        self.assertEqual(cashier_pos.status_code, 200)
        self.assertTemplateUsed(cashier_pos, 'sales/cashier_orders.html')
        self.assertEqual(self.client.get(reverse('tables')).status_code, 403)
        self.assertEqual(self.client.get(reverse('inventory')).status_code, 403)

        self.client.force_login(self.chef)
        self.assertEqual(self.client.get(reverse('pos')).status_code, 403)
        self.assertEqual(self.client.get(reverse('inventory')).status_code, 403)
        self.assertEqual(self.client.get(reverse('kitchen')).status_code, 200)

    def test_owner_can_create_employee_for_selected_branch_but_manager_cannot_escalate_role(self):
        self.client.force_login(self.owner)
        created = self.client.post(reverse('staff_create'), {
            'username': 'branch-waiter',
            'password': 'strong-password-123',
            'first_name': 'Mesero',
            'last_name': 'Prueba',
            'email': 'waiter@example.com',
            'role': User.Role.WAITER,
            'branch': self.branch.id,
        })
        self.assertEqual(created.status_code, 302)
        employee = User.objects.get(username='branch-waiter')
        self.assertEqual(employee.restaurant_id, self.restaurant.id)
        self.assertEqual(employee.branch_id, self.branch.id)
        self.assertFalse(employee.is_staff)
        self.assertFalse(employee.is_superuser)

        self.client.force_login(self.manager)
        escalation = self.client.post(reverse('staff_create'), {
            'username': 'manager-escalation',
            'password': 'strong-password-123',
            'first_name': 'Admin',
            'last_name': 'Ajeno',
            'email': 'admin@example.com',
            'role': User.Role.ADMIN,
        })
        self.assertEqual(escalation.status_code, 403)
        self.assertFalse(User.objects.filter(username='manager-escalation').exists())

    def test_staff_member_flag_does_not_grant_global_django_admin(self):
        self.manager.is_staff = True
        self.manager.save(update_fields=['is_staff'])
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get('/admin/').status_code, 403)

    def test_system_plans_are_not_accessible_to_restaurant_staff(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get('/api/plans/').status_code, 403)
        self.assertEqual(self.client.post('/api/restaurants/', {}, format='json').status_code, 403)

    def test_manager_api_user_list_and_role_assignment_stay_in_branch_scope(self):
        other_branch = Branch.objects.create(restaurant=self.restaurant, name='Otra sucursal')
        other_user = User.objects.create_user(
            username='other-branch-user', password='strong-password-123',
            role=User.Role.WAITER, restaurant=self.restaurant, branch=other_branch,
        )
        self.client.force_authenticate(self.manager)

        response = self.client.get('/api/users/')
        usernames = [row['username'] for row in response.data['results']]
        self.assertNotIn(other_user.username, usernames)

        denied = self.client.post('/api/users/', {
            'username': 'api-escalation',
            'password': 'strong-password-123',
            'role': User.Role.ADMIN,
        }, format='json')
        self.assertEqual(denied.status_code, 400)
        self.assertFalse(User.objects.filter(username='api-escalation').exists())

    @override_settings(DEBUG=True)
    def test_demo_command_creates_all_roles_and_only_one_system_superuser(self):
        call_command('create_demo_profiles', stdout=StringIO())
        demo_users = User.objects.filter(username__startswith='bemba_demo_')
        self.assertEqual(demo_users.count(), 6)
        self.assertEqual(demo_users.filter(is_superuser=True).count(), 1)
        self.assertEqual(demo_users.filter(is_staff=True, is_superuser=False).count(), 0)

    def test_employee_without_tenant_scope_cannot_open_dashboard_or_kitchen(self):
        unassigned = User.objects.create_user(
            username='unassigned-chef', password='strong-password-123', role=User.Role.CHEF,
        )
        self.client.force_login(unassigned)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 403)
        self.assertEqual(self.client.get(reverse('kitchen')).status_code, 403)

    def test_cashier_cannot_create_orders(self):
        self.client.force_authenticate(self.cashier)
        response = self.client.post('/api/orders/', {}, format='json')
        self.assertEqual(response.status_code, 403)
