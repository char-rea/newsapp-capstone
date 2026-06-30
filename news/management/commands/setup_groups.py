from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from news.models import Article, Newsletter


class Command(BaseCommand):
    """
    Creates the Reader, Editor, and Journalist groups with correct permissions.
    Run once after migrations: python manage.py setup_groups
    """
    help = "Set up default role groups and assign permissions."

    def handle(self, *args, **kwargs):
        self._create_reader_group()
        self._create_editor_group()
        self._create_journalist_group()
        self.stdout.write(self.style.SUCCESS("✓ Groups and permissions configured."))

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_perms(self, model, actions):
        """Return a list of Permission objects for the given model and actions."""
        ct = ContentType.objects.get_for_model(model)
        perms = []
        for action in actions:
            try:
                perms.append(Permission.objects.get(codename=f"{action}_{model.__name__.lower()}", content_type=ct))
            except Permission.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  Permission '{action}_{model.__name__.lower()}' not found."))
        return perms

    def _create_reader_group(self):
        """Readers can only view articles and newsletters."""
        group, created = Group.objects.get_or_create(name='Reader')
        group.permissions.set(
            self._get_perms(Article, ['view']) +
            self._get_perms(Newsletter, ['view'])
        )
        self.stdout.write(f"  {'Created' if created else 'Updated'} Reader group.")

    def _create_editor_group(self):
        """Editors can view, change, and delete articles and newsletters."""
        group, created = Group.objects.get_or_create(name='Editor')
        group.permissions.set(
            self._get_perms(Article,     ['view', 'change', 'delete']) +
            self._get_perms(Newsletter,  ['view', 'change', 'delete'])
        )
        self.stdout.write(f"  {'Created' if created else 'Updated'} Editor group.")

    def _create_journalist_group(self):
        """Journalists have full CRUD on articles and newsletters."""
        group, created = Group.objects.get_or_create(name='Journalist')
        group.permissions.set(
            self._get_perms(Article,    ['add', 'view', 'change', 'delete']) +
            self._get_perms(Newsletter, ['add', 'view', 'change', 'delete'])
        )
        self.stdout.write(f"  {'Created' if created else 'Updated'} Journalist group.")