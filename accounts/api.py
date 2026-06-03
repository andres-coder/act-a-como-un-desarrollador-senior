from django.contrib.auth import get_user_model
from rest_framework import serializers, viewsets

from accounts.permissions import IsAdminOrManager


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'restaurant', 'branch', 'role', 'phone', 'is_active_employee', 'password']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        if self.request.user.is_superuser or not self.request.user.restaurant_id:
            return super().get_queryset()
        return super().get_queryset().filter(restaurant=self.request.user.restaurant)
