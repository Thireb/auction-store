from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from apps.core.roles import ROLES


class Command(BaseCommand):
    help = "Create the default staff groups and add their permissions. Safe to run again."

    def handle(self, *args, **options):
        for role, perm_names in ROLES.items():
            group, created = Group.objects.get_or_create(name=role)
            perms, missing = [], []
            for name in perm_names:
                app_label, codename = name.split(".", 1)
                perm = Permission.objects.filter(
                    content_type__app_label=app_label, codename=codename
                ).first()
                if perm:
                    perms.append(perm)
                else:
                    missing.append(name)
            group.permissions.add(*perms)
            action = "Created" if created else "Updated"
            self.stdout.write(f"{action} group '{role}': {len(perms)} permissions added.")
            if missing:
                self.stdout.write(f"  Skipped {len(missing)} permissions (model not built yet).")
