from django.conf import settings
from django.db import models

from allauth.socialaccount.models import SocialAccount

from .providers import (
    FacebookServiceProvider,
    GoogleServiceProvider,
    MicrosoftServiceProvider,
)


class Scope(models.Model):
    name = models.CharField(max_length=255)
    provider = models.CharField(max_length=255)
    required = models.BooleanField(default=False)

    grants_access = models.BooleanField(default=False)
    access_type = models.CharField(max_length=255, default='default')

    def __str__(self):
        return f'{self.provider}: {self.name}'


class UserProviderScope(models.Model):
    scope = models.ForeignKey(Scope, on_delete=models.CASCADE)

    account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE, related_name='+')

    inserted = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.scope}'


class Service(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE)

    inserted = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._service_provider = None

    @property
    def name(self):
        return str(self)

    def __str__(self):
        service_provider = self.get_service_provider()
        if service_provider:
            email = service_provider.get_email()
            if email:
                email, _, domain = email.partition('@')
                if domain not in service_provider.primary_email_domains:
                    return f"{service_provider.provider_name} ({email}@{domain})"
                return f"{service_provider.provider_name} ({email})"
            return service_provider.provider_name
        else:
            return self.account.get_provider().name

    def get_service_provider(self):
        if not self._service_provider:
            if self.account.provider == 'google':
                self._service_provider = GoogleServiceProvider(account=self.account)
            elif self.account.provider == 'microsoft':
                self._service_provider = MicrosoftServiceProvider(account=self.account)
            elif self.account.provider == 'facebook':
                self._service_provider = FacebookServiceProvider(account=self.account)
        return self._service_provider

#     def get_settings(self):
#         return
#
#
# class ProviderSetting(models.Model):
#     pass
