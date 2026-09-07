import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from invoices.models import StaffProfile, Role


class Command(BaseCommand):
    """
    Run automatically as part of the Render build command (see render.yaml).
    Reads BOOTSTRAP_ADMIN_USERNAME / BOOTSTRAP_ADMIN_PASSWORD /
    BOOTSTRAP_ADMIN_EMAIL from the environment. Exists specifically because
    the free Render tier has no Shell access to run createsuperuser
    interactively. Idempotent — safe to run on every single deploy; it only
    actually creates anything the first time.
    """
    help = "Creates the initial superuser + StaffProfile(role=Administrator) from env vars, if they don't already exist."

    def handle(self, *args, **options):
        username = os.environ.get('BOOTSTRAP_ADMIN_USERNAME')
        password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD')
        email = os.environ.get('BOOTSTRAP_ADMIN_EMAIL', '')

        if not username or not password:
            self.stdout.write(self.style.WARNING(
                'BOOTSTRAP_ADMIN_USERNAME / BOOTSTRAP_ADMIN_PASSWORD not set — skipping.'
            ))
            return

        try:
            admin_role = Role.objects.get(name='Administrator')
        except Role.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                'No "Administrator" Role found — did the seed_roles migration (0008) run? Run python manage.py migrate first.'
            ))
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email, 'is_staff': True, 'is_superuser': True},
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created superuser "{username}".'))
        else:
            self.stdout.write(f'User "{username}" already exists — left as-is.')

        _, profile_created = StaffProfile.objects.get_or_create(
            user=user, defaults={
                'role': admin_role,
                'privileges': list(admin_role.defaultPrivileges),
            }
        )
        if profile_created:
            self.stdout.write(self.style.SUCCESS('Created StaffProfile(role=Administrator).'))
        else:
            self.stdout.write('StaffProfile already existed — left as-is.')