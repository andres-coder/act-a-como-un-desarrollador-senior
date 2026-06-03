from rest_framework import serializers, viewsets

from accounts.permissions import IsPOSStaff
from restaurant.models import Branch, DiningTable, RestaurantAccount, SubscriptionPlan, Zone
from restaurant.tenancy import scoped_queryset


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'


class RestaurantAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantAccount
        fields = '__all__'


class BranchSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source='restaurant.business_name', read_only=True)

    class Meta:
        model = Branch
        fields = '__all__'


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zone
        fields = '__all__'


class DiningTableSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    branch_name = serializers.CharField(source='zone.branch.name', read_only=True)

    class Meta:
        model = DiningTable
        fields = ['id', 'zone', 'zone_name', 'branch_name', 'number', 'seats', 'status', 'is_active']


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsPOSStaff]


class RestaurantAccountViewSet(viewsets.ModelViewSet):
    queryset = RestaurantAccount.objects.select_related('plan')
    serializer_class = RestaurantAccountSerializer
    permission_classes = [IsPOSStaff]

    def get_queryset(self):
        return scoped_queryset(super().get_queryset(), self.request.user, 'id')


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.select_related('restaurant')
    serializer_class = BranchSerializer
    permission_classes = [IsPOSStaff]

    def get_queryset(self):
        return scoped_queryset(super().get_queryset(), self.request.user)


class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer
    permission_classes = [IsPOSStaff]

    def get_queryset(self):
        return scoped_queryset(super().get_queryset(), self.request.user, 'branch__restaurant')


class DiningTableViewSet(viewsets.ModelViewSet):
    queryset = DiningTable.objects.select_related('zone__branch__restaurant')
    serializer_class = DiningTableSerializer
    permission_classes = [IsPOSStaff]

    def get_queryset(self):
        return scoped_queryset(super().get_queryset(), self.request.user, 'zone__branch__restaurant')
