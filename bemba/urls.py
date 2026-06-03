"""
URL configuration for bemba project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.api import UserViewSet
from inventory.api import CategoryViewSet, IngredientViewSet, MenuItemViewSet, StockMovementViewSet
from restaurant.api import BranchViewSet, DiningTableViewSet, RestaurantAccountViewSet, SubscriptionPlanViewSet, ZoneViewSet
from sales.api import OrderViewSet, PaymentViewSet

router = DefaultRouter()
router.register('users', UserViewSet)
router.register('plans', SubscriptionPlanViewSet)
router.register('restaurants', RestaurantAccountViewSet)
router.register('branches', BranchViewSet)
router.register('zones', ZoneViewSet)
router.register('tables', DiningTableViewSet)
router.register('categories', CategoryViewSet)
router.register('ingredients', IngredientViewSet)
router.register('menu-items', MenuItemViewSet)
router.register('stock-movements', StockMovementViewSet)
router.register('orders', OrderViewSet)
router.register('payments', PaymentViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('accounts/', include('accounts.urls')),
    path('restaurant/', include('restaurant.urls')),
    path('pos/', include('sales.urls')),
    path('kitchen/', include('kitchen.urls')),
    path('inventory/', include('inventory.urls')),
    path('reports/', include('reports.urls')),
    path('api/', include(router.urls)),
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
