# users/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator

# 1. Role Model (stores user roles like Admin, Manager, User)
class Role(models.Model):
    name = models.CharField(max_length=50, unique=True, help_text="e.g., Admin, Manager, User")

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'accounts_role'                          # Explicit table name


# 2. Custom User Model (replaces default auth.User)
class User(AbstractUser):
    # username and password are inherited from AbstractUser.
    # Django stores password as a hash (password_hash internally).
    # We add 'role_id' as a foreign key to Role.
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,                 # If a role is deleted, set to NULL
        null=True,                                 # Allow null for users without a role
        blank=True,
        db_column='role_id'                        # Explicit column name to match task spec
    )

    # Override the default groups and user_permissions if needed (optional)
    # groups = models.ManyToManyField(...) # We'll keep default

    class Meta:
        db_table = 'accounts_user'                          # Table name matches task spec
        # username is already unique by default in AbstractUser
        # password is NOT NULL by default

    def __str__(self):
        return self.username