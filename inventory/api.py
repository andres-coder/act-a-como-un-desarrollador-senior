from rest_framework import serializers, viewsets
from django.db import transaction

from accounts.permissions import IsAdminOrManager
from inventory.models import (
    Category,
    Ingredient,
    MenuItem,
    RecipeItem,
    StockMovement
)
from restaurant.tenancy import scoped_queryset


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'
        read_only_fields = ['restaurant']


class IngredientSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Ingredient
        fields = '__all__'
        read_only_fields = ['restaurant']


class RecipeItemSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(
        source='ingredient.name',
        read_only=True
    )

    class Meta:
        model = RecipeItem
        fields = [
            'id',
            'ingredient',
            'ingredient_name',
            'quantity'
        ]

    def validate(self, attrs):
        user = self.context['request'].user
        category = attrs.get('category', getattr(self.instance, 'category', None))
        if not user.is_superuser and category.restaurant_id != user.restaurant_id:
            raise serializers.ValidationError({'category': 'La categoría debe pertenecer a tu restaurante.'})
        for row in attrs.get('recipe', []):
            if not user.is_superuser and row['ingredient'].restaurant_id != user.restaurant_id:
                raise serializers.ValidationError({'recipe': 'Los ingredientes deben pertenecer a tu restaurante.'})
        return attrs


class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source='category.name',
        read_only=True
    )

    recipe = RecipeItemSerializer(
        many=True,
        required=False
    )

    class Meta:
        model = MenuItem
        fields = [
            'id',
            'category',
            'category_name',
            'name',
            'description',
            'price',
            'tax_rate',
            'image_url',
            'is_available',
            'is_kitchen_item',
            'recipe'
        ]

    def create(self, validated_data):
        recipe_data = validated_data.pop('recipe', [])

        user = self.context['request'].user

        menu_item = MenuItem.objects.create(
            restaurant=user.restaurant,
            **validated_data
        )

        for row in recipe_data:
            RecipeItem.objects.create(
                menu_item=menu_item,
                **row
            )

        return menu_item

    def update(self, instance, validated_data):
        recipe_data = validated_data.pop('recipe', None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()

        if recipe_data is not None:
            instance.recipe.all().delete()

            for row in recipe_data:
                RecipeItem.objects.create(
                    menu_item=instance,
                    **row
                )

        return instance


class StockMovementSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(
        source='ingredient.name',
        read_only=True
    )

    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = StockMovement
        fields = '__all__'
        read_only_fields = [
            'created_by',
            'created_at',
            'restaurant'
        ]

    def validate(self, attrs):
        user = self.context['request'].user
        ingredient = attrs.get('ingredient', getattr(self.instance, 'ingredient', None))
        movement_type = attrs.get('movement_type', getattr(self.instance, 'movement_type', None))
        quantity = attrs.get('quantity', getattr(self.instance, 'quantity', None))
        if not user.is_superuser and ingredient.restaurant_id != user.restaurant_id:
            raise serializers.ValidationError({'ingredient': 'El ingrediente no pertenece a tu restaurante.'})
        if movement_type == StockMovement.Type.SALE:
            raise serializers.ValidationError({'movement_type': 'Las salidas por venta se generan al registrar el pago.'})
        if quantity is not None and quantity <= 0:
            raise serializers.ValidationError({'quantity': 'La cantidad debe ser mayor que cero.'})
        if movement_type == StockMovement.Type.OUT and ingredient.current_stock < quantity:
            raise serializers.ValidationError({'quantity': 'No hay existencias suficientes para esta salida.'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user

        movement = StockMovement.objects.create(
            created_by=user,
            restaurant=user.restaurant,
            **validated_data
        )

        ingredient = movement.ingredient

        if movement.movement_type == StockMovement.Type.IN:
            ingredient.current_stock += movement.quantity
        else:
            ingredient.current_stock -= movement.quantity

        ingredient.save(update_fields=['current_stock'])

        return movement


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()

    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        return scoped_queryset(
            self.queryset,
            self.request.user
        )

    def perform_create(self, serializer):
        serializer.save(
            restaurant=self.request.user.restaurant
        )


class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()

    serializer_class = IngredientSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        return scoped_queryset(
            self.queryset,
            self.request.user
        )

    def perform_create(self, serializer):
        serializer.save(
            restaurant=self.request.user.restaurant
        )


class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.select_related(
        'category'
    ).prefetch_related(
        'recipe__ingredient'
    )

    serializer_class = MenuItemSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        return scoped_queryset(
            self.queryset,
            self.request.user
        )

    def perform_create(self, serializer):
        serializer.save(
            restaurant=self.request.user.restaurant
        )


class StockMovementViewSet(viewsets.ModelViewSet):

    http_method_names = ['get', 'post', 'head', 'options']
    queryset = StockMovement.objects.select_related(
        'ingredient',
        'created_by'
    )

    serializer_class = StockMovementSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):

        qs = super().get_queryset()

        user = self.request.user

        if user.is_superuser:
            return qs

        # ADMIN
        if user.role == 'admin':
            return qs.filter(
                restaurant=user.restaurant
            )

        # MANAGER
        if user.role == 'manager':
            return qs.filter(
                created_by__branch=user.branch
            )

        return qs.none()
