#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bemba.settings')
django.setup()

from sales.models import Payment, Order
from restaurant.models import RestaurantAccount
from accounts.models import User
from datetime import datetime, timedelta
from django.utils import timezone
import random

try:
    restaurant = RestaurantAccount.objects.first()
    branch = restaurant.branches.first()
    user = User.objects.filter(role='cashier').first()
    
    if not restaurant or not branch or not user:
        print("Error: No hay datos de restaurant, branch o usuario")
    else:
        # Crear 5 pagos en junio
        created = 0
        for i in range(5):
            date = timezone.make_aware(datetime(2026, 6, 1) + timedelta(hours=i*2))
            amount = round(random.uniform(10000, 100000), 2)
            
            order = Order.objects.create(
                restaurant=restaurant,
                branch=branch,
                total=amount,
                status='completed'
            )
            
            payment = Payment.objects.create(
                order=order,
                amount=amount,
                method=random.choice(['cash', 'card', 'transfer']),
                cashier=user,
                created_at=date
            )
            print(f'Creado pago {i+1}: {date} - ${amount}')
            created += 1
        
        # Verificar
        june_count = Payment.objects.filter(
            created_at__gte=timezone.make_aware(datetime(2026, 6, 1, 0, 0, 0)),
            created_at__lt=timezone.make_aware(datetime(2026, 6, 2, 0, 0, 0))
        ).count()
        print(f'\nTotal pagos creados: {created}')
        print(f'Total pagos en junio 1: {june_count}')
        print(f'Total pagos en BD: {Payment.objects.count()}')
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
