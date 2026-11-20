from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        OPERATOR = "OPERATOR", "System Operator"
        VIEWER = "VIEWER", "Viewer"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)

    REQUIRED_FIELDS = ["email"]

    def is_administrator(self):
        return self.role == self.Role.ADMIN