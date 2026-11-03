from rest_framework import serializers, viewsets

from accounts.permissions import (
    IsBranchStaffReadOnly,
    IsSystemAdmin,
    IsTenantOwnerReadOnly,
)
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
        read_only_fields = ['restaurant']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_superuser:
            self.fields['restaurant'].read_only = False


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zone
        fields = '__all__'

    def validate_branch(self, value):
        user = self.context['request'].user
        if value is None:
            raise serializers.ValidationError('La zona debe estar asignada a una sucursal.')
        if not user.is_superuser and value.restaurant_id != user.restaurant_id:
            raise serializers.ValidationError('La sucursal no pertenece a tu restaurante.')
        if user.role == 'manager' and value.id != user.branch_id:
            raise serializers.ValidationError('Solo puedes administrar zonas de tu sucursal.')
        return value


class DiningTableSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    branch_name = serializers.CharField(source='zone.branch.name', read_only=True)

    class Meta:
        model = DiningTable
        fields = ['id', 'zone', 'zone_name', 'branch_name', 'number', 'seats', 'status', 'is_active']

    def validate_zone(self, value):
        user = self.context['request'].user
        branch = value.branch
        if not branch:
            raise serializers.ValidationError('La zona debe pertenecer a una sucursal.')
        if not user.is_superuser and branch.restaurant_id != user.restaurant_id:
            raise serializers.ValidationError('La sucursal no pertenece a tu restaurante.')
        if user.role == 'manager' and branch.id != user.branch_id:
            raise serializers.ValidationError('Solo puedes administrar mesas de tu sucursal.')
        return value


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsSystemAdmin]


class RestaurantAccountViewSet(viewsets.ModelViewSet):
    queryset = RestaurantAccount.objects.select_related('plan')
    serializer_class = RestaurantAccountSerializer
    permission_classes = [IsTenantOwnerReadOnly]

    def get_queryset(self):
        return scoped_queryset(super().get_queryset(), self.request.user, 'id')


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.select_related('restaurant')
    serializer_class = BranchSerializer
    permission_classes = [IsBranchStaffReadOnly]

    def get_queryset(self):
        return scoped_queryset(super().get_queryset(), self.request.user)

    def perform_create(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
        else:
            serializer.save(restaurant=self.request.user.restaurant)


class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer
    permission_classes = [IsBranchStaffReadOnly]

    def get_queryset(self):
        return scoped_queryset(super().get_queryset(), self.request.user, 'branch__restaurant')


class DiningTableViewSet(viewsets.ModelViewSet):
    queryset = DiningTable.objects.select_related('zone__branch__restaurant')
    serializer_class = DiningTableSerializer
    permission_classes = [IsBranchStaffReadOnly]

    def get_queryset(self):
        return scoped_queryset(super().get_queryset(), self.request.user, 'zone__branch__restaurant')
