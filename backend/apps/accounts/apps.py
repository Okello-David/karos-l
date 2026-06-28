from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_default_groups(sender, **kwargs):
    from django.contrib.auth.models import Group

    groups = ["Property Manager", "Staff"]
    for name in groups:
        Group.objects.get_or_create(name=name)


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    label = 'accounts'

    def ready(self):
        post_migrate.connect(create_default_groups, sender=self)
