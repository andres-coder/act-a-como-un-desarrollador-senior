from django.urls import path

from kitchen.views import kitchen_board, update_ticket_status

urlpatterns = [
    path('', kitchen_board, name='kitchen'),
    path('ticket/<int:order_id>/status/', update_ticket_status, name='kitchen_update_status'),
]