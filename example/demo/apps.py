from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.core.management import call_command


def setup_default_scopes(**kwargs):
    from service_interactor.models import Scope

    if not Scope.objects.exists():
        call_command('loaddata', 'Scope')


class DemoConfig(AppConfig):
    name = 'demo'

    def ready(self):
        post_migrate.connect(setup_default_scopes)
