from django.urls import path

from restaurant.views import tables

urlpatterns = [
    path('tables/', tables, name='tables'),
]
