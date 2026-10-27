import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from common.constants import Role

User = get_user_model()


class Command(BaseCommand):
    """
    Creates (or updates) the initial Super Admin account.

    Usage:
        python manage.py bootstrap_superadmin \
            --username admin --email admin@college.edu --password ...

    Values can also come from SSM_SUPERADMIN_USERNAME / _EMAIL / _PASSWORD
    environment variables so this can run unattended in a deploy script.
    Idempotent: re-running just ensures the account exists with role
    SUPER_ADMIN and is active.
    """

    help = "Create the initial Super Admin account (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=os.environ.get("SSM_SUPERADMIN_USERNAME", "superadmin"))
        parser.add_argument("--email", default=os.environ.get("SSM_SUPERADMIN_EMAIL", "superadmin@example.com"))
        parser.add_argument("--password", default=os.environ.get("SSM_SUPERADMIN_PASSWORD"))

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]
        password = options["password"]

        if not password:
            self.stderr.write(self.style.ERROR(
                "No password provided. Pass --password or set SSM_SUPERADMIN_PASSWORD."
            ))
            return

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "role": Role.SUPER_ADMIN, "is_staff": True, "is_superuser": True},
        )
        user.role = Role.SUPER_ADMIN
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.email = email
        user.set_password(password)
        user.save()

        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} Super Admin '{username}'."))
