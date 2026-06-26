from django.db import models


class BillingMode(models.TextChoices):
    SEMESTER = 'semester', 'Semester'
    MONTHLY = 'monthly', 'Monthly'


class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Cash'
    BANK_TRANSFER = 'transfer', 'Bank Transfer'
    CARD = 'card', 'Card'
