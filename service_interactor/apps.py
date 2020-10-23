from django.apps import AppConfig


class ServiceInteractorConfig(AppConfig):
    name = 'service_interactor'

    def ready(self):
        from . import signals  # noqa
