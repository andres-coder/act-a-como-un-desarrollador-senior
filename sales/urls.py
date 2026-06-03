from django.urls import path

from sales.views import checkout, pos, ticket

urlpatterns = [
    path('', pos, name='pos'),
    path('checkout/<int:pk>/', checkout, name='checkout'),
    path('ticket/<int:pk>/', ticket, name='ticket'),
]
