import os
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from inventory.models import Category, Ingredient, MenuItem, RecipeItem
from kitchen.models import KitchenTicket
from restaurant.models import Branch, DiningTable, RestaurantAccount, SubscriptionPlan, Zone
from sales.models import Order, OrderItem


class Command(BaseCommand):
    help = 'Crea perfiles y datos de prueba locales para cada rol de Bemba POS.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Este comando solo se puede ejecutar con DEBUG=True, por ejemplo settings_dev.')

        password = os.getenv('BEMBA_DEMO_PASSWORD', 'BembaDemo2026!')
        plan, _ = SubscriptionPlan.objects.get_or_create(
            name='Plan Bemba Demo',
            defaults={'max_branches': 3, 'max_users': 20},
        )
        restaurant, _ = RestaurantAccount.objects.get_or_create(
            business_name='Restaurante demo Bemba',
            defaults={
                'plan': plan,
                'email': 'demo@bemba.local',
                'status': RestaurantAccount.Status.ACTIVE,
            },
        )
        branch, _ = Branch.objects.get_or_create(
            restaurant=restaurant,
            name='Sucursal Demo',
        )

        system_admin = User.objects.filter(is_superuser=True).first()
        if system_admin is None:
            system_admin = User.objects.create_superuser(
                username='bemba_demo_superadmin',
                email='superadmin@bemba.local',
                password=password,
                role=User.Role.ADMIN,
            )
            self.stdout.write('bemba_demo_superadmin: creado como superadministrador local')
        else:
            self.stdout.write('Se conservó el superadministrador existente.')
            if system_admin.username == 'bemba_demo_superadmin' and system_admin.role != User.Role.ADMIN:
                system_admin.role = User.Role.ADMIN
                system_admin.save(update_fields=['role'])

        profiles = {
            'bemba_demo_owner': (User.Role.ADMIN, None),
            'bemba_demo_manager': (User.Role.MANAGER, branch),
            'bemba_demo_cashier': (User.Role.CASHIER, branch),
            'bemba_demo_waiter': (User.Role.WAITER, branch),
            'bemba_demo_chef': (User.Role.CHEF, branch),
        }
        for username, (role, assigned_branch) in profiles.items():
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'role': role,
                    'restaurant': restaurant,
                    'branch': assigned_branch,
                    'is_active': True,
                    'is_active_employee': True,
                },
            )
            if user.is_superuser or user.is_staff:
                raise CommandError(f'El usuario reservado {username} ya tiene privilegios del sistema; no se modificó.')
            user.role = role
            user.restaurant = restaurant
            user.branch = assigned_branch
            user.is_active = True
            user.is_active_employee = True
            user.set_password(password)
            user.save(update_fields=[
                'role', 'restaurant', 'branch', 'is_active', 'is_active_employee', 'password',
            ])
            state = 'creado' if created else 'actualizado'
            self.stdout.write(f'{username}: {state}, rol {role}')

        zone, _ = Zone.objects.get_or_create(branch=branch, name='Salón Demo')
        tables = []
        for number in ('D1', 'D2'):
            table, _ = DiningTable.objects.get_or_create(zone=zone, number=number)
            tables.append(table)

        category, _ = Category.objects.get_or_create(
            restaurant=restaurant,
            name='Menú Demo',
            defaults={'is_active': True},
        )
        ingredient, _ = Ingredient.objects.get_or_create(
            restaurant=restaurant,
            name='Insumo Demo',
            defaults={
                'unit': Ingredient.Unit.UNIT,
                'current_stock': Decimal('100.000'),
                'min_stock': Decimal('5.000'),
            },
        )
        menu_item, _ = MenuItem.objects.get_or_create(
            restaurant=restaurant,
            name='Plato Demo',
            defaults={
                'category': category,
                'price': Decimal('10000.00'),
                'is_available': True,
            },
        )
        RecipeItem.objects.get_or_create(
            menu_item=menu_item,
            ingredient=ingredient,
            defaults={'quantity': Decimal('0.100')},
        )

        waiter = User.objects.get(username='bemba_demo_waiter')
        for table, status, note in [
            (tables[0], Order.Status.READY, 'BEMBA DEMO LISTO'),
            (tables[1], Order.Status.SENT, 'BEMBA DEMO COCINA'),
        ]:
            order = Order.objects.filter(
                restaurant=restaurant,
                notes=note,
            ).exclude(status__in=[Order.Status.PAID, Order.Status.CANCELLED]).first()
            if order is None:
                order = Order.objects.create(
                    restaurant=restaurant,
                    branch=branch,
                    table=table,
                    waiter=waiter,
                    status=status,
                    notes=note,
                )
                OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=1,
                    unit_price=menu_item.price,
                    tax_rate=menu_item.tax_rate,
                )
            KitchenTicket.objects.get_or_create(
                order=order,
                defaults={
                    'status': (
                        KitchenTicket.Status.READY
                        if status == Order.Status.READY
                        else KitchenTicket.Status.PENDING
                    ),
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f'Perfiles demo listos. Contraseña local común: {password}. '
            f'Superadministrador local: {system_admin.username}.'
        ))
