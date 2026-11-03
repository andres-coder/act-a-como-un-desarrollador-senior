from django.db import models


class SubscriptionPlan(models.Model):
    class BillingCycle(models.TextChoices):
        MONTHLY = 'monthly', 'Mensual'
        YEARLY = 'yearly', 'Anual'

    name = models.CharField(max_length=80, unique=True)
    monthly_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_branches = models.PositiveSmallIntegerField(default=1)
    max_users = models.PositiveSmallIntegerField(default=5)
    billing_cycle = models.CharField(
        max_length=20,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['monthly_price', 'name']

    def __str__(self):
        return self.name


class RestaurantAccount(models.Model):
    class Status(models.TextChoices):
        TRIAL = 'trial', 'Prueba'
        ACTIVE = 'active', 'Activa'
        PAST_DUE = 'past_due', 'Pago vencido'
        SUSPENDED = 'suspended', 'Suspendida'
        CANCELLED = 'cancelled', 'Cancelada'

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='restaurants'
    )

    business_name = models.CharField(max_length=160)

    legal_name = models.CharField(
        max_length=160,
        blank=True
    )

    tax_id = models.CharField(
        max_length=40,
        blank=True
    )

    nit = models.CharField(
        max_length=50,
        blank=True
    )

    email = models.EmailField(
        blank=True
    )

    phone = models.CharField(
        max_length=30,
        blank=True
    )

    address = models.CharField(
        max_length=255,
        blank=True
    )

    website = models.URLField(
        blank=True
    )

    logo = models.ImageField(
        upload_to='restaurants/logos/',
        blank=True,
        null=True
    )

    primary_color = models.CharField(
        max_length=20,
        default='#3b2416'
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TRIAL
    )

    subscription_started_at = models.DateField(
        blank=True,
        null=True
    )

    subscription_ends_at = models.DateField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['business_name']

    def __str__(self):
        return self.business_name


class Branch(models.Model):
    restaurant = models.ForeignKey(
        RestaurantAccount,
        on_delete=models.CASCADE,
        related_name='branches'
    )

    name = models.CharField(max_length=100)

    address = models.CharField(
        max_length=180,
        blank=True
    )

    phone = models.CharField(
        max_length=30,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('restaurant', 'name')
        ordering = ['restaurant__business_name', 'name']

    def __str__(self):
        return f'{self.restaurant} - {self.name}'


class Zone(models.Model):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='zones',
        blank=True,
        null=True
    )

    name = models.CharField(max_length=80)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('branch', 'name')
        ordering = ['name']

    def __str__(self):
        return self.name


class DiningTable(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Disponible'
        OCCUPIED = 'occupied', 'Ocupada'
        RESERVED = 'reserved', 'Reservada'
        CLEANING = 'cleaning', 'Limpieza'

    zone = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name='tables'
    )

    number = models.CharField(max_length=20)

    seats = models.PositiveSmallIntegerField(default=4)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('zone', 'number')
        ordering = ['zone__name', 'number']

    def __str__(self):
        return f'{self.zone} - Mesa {self.number}'


# Create your models here.