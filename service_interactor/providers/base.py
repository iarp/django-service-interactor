from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import mark_safe

from allauth.socialaccount.models import SocialAccount, SocialApp

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


class ServiceProvider(object):
    provider_id = None
    provider_name = None

    primary_email_domains = []

    token_uri = None
    requires_token_secret = False

    def __init__(self, account: SocialAccount):
        self.client = SocialApp.objects.get(provider=self.provider_id)
        self.account = account
        self.token = self._get_social_token()

    @cached_property
    def credentials(self):

        if not self.token_uri:
            raise ValueError(f'Missing token_uri attribute on {self.__class__.__name__} class')
        if not self.token:
            raise ValueError(f'Invalid Social Token for {self.__class__.__name__}')
        if not self.token.token_secret:
            raise ValueError('Token Refresh Missing')

        creds = Credentials(
            token=self.token.token,
            refresh_token=self.token.token_secret,
            # scopes=settings.SOCIALACCOUNT_PROVIDERS['google']['SCOPE'],
            scopes=list(self.get_account_scopes().values_list('scope__name', flat=True)),
            token_uri=self.token_uri,

            client_id=self.client.client_id,
            client_secret=self.client.secret
        )
        creds.expiry = timezone.make_naive(self.token.expires_at)

        if not creds.valid or creds.expired:
            self._refresh_token(creds)

        return creds

    def _refresh_token(self, credentials):
        print('Refreshing', self.account, self.account.provider)
        credentials.refresh(Request())

        if credentials.expiry:
            self.token.expires_at = timezone.make_aware(credentials.expiry)

        if credentials.refresh_token:
            self.token.token_secret = credentials.refresh_token

        self.token.token = credentials.token
        self.token.save()

    def _get_social_token(self):
        for token in self.account.socialtoken_set.all().order_by('-expires_at'):
            return token

    def get_account_scopes(self, **kwargs):
        from ..models import UserProviderScope
        return UserProviderScope.objects.filter(account=self.account, **kwargs)

    @classmethod
    def get_provider_scopes(cls, **kwargs):
        from ..models import Scope
        return Scope.objects.filter(provider=cls.provider_id, **kwargs)

    def get_new_scopes(self, **kwargs):
        scopes = set()
        for es in self.get_account_scopes():
            scopes.add(es.scope.name)
        if kwargs:
            for s in self.get_provider_scopes(**kwargs):
                scopes.add(s.name)
        return scopes

    def setup_default_scopes(self):
        from ..models import UserProviderScope
        for scope in self.get_provider_scopes(required=True):
            UserProviderScope.objects.get_or_create(
                account=self.account,
                scope=scope
            )

    def get_calendar_access_granted_datetime(self):
        for es in self.get_account_scopes(scope__access_type='calendar', scope__grants_access=True):
            return es.inserted

    def get_files_access_granted_datetime(self):
        for es in self.get_account_scopes(scope__access_type='files', scope__grants_access=True):
            return es.inserted

    def get_email(self):
        return self.account.extra_data.get('email')

    @property
    def is_enabled(self):
        if self.requires_token_secret:
            return self.token and self.token.token
        return self.token

    @property
    def has_calendar_access(self):
        return self.provider_has_calendar_abilities and self.is_enabled and \
               self.get_account_scopes().filter(scope__access_type='calendar', scope__grants_access=True).exists()

    @property
    def has_file_access(self):
        return self.provider_has_files_abilities and self.is_enabled and \
               self.get_account_scopes().filter(scope__access_type='files', scope__grants_access=True).exists()

    @property
    def has_youtube_access(self):
        return self.provider_has_youtube_abilities and self.is_enabled and \
               self.get_account_scopes().filter(scope__access_type='youtube', scope__grants_access=True).exists()

    @property
    def provider_has_calendar_abilities(self):
        return self.get_provider_scopes(access_type='calendar').exists()

    @property
    def provider_has_files_abilities(self):
        return self.get_provider_scopes(access_type='files').exists()

    @property
    def provider_has_youtube_abilities(self):
        return self.get_provider_scopes(access_type='youtube').exists()

    def get_current_access_scopes_url(self):
        return mark_safe(','.join(self.get_new_scopes()))

    def get_files_access_scopes_url(self):
        return mark_safe(','.join(self.get_new_scopes(access_type='files')))

    def get_calendar_access_scopes_url(self):
        return mark_safe(','.join(self.get_new_scopes(access_type='calendar')))

    def get_youtube_access_scopes_url(self):
        return mark_safe(','.join(self.get_new_scopes(access_type='youtube')))

    def get_files(self, **kwargs):
        raise NotImplementedError

    def get_calendars(self):
        raise NotImplementedError

    def get_calendar_events(self, **kwargs):
        raise NotImplementedError

    def create_calendar_event(self, *args, **kwargs):
        raise NotImplementedError

    def delete_calendar_event(self, calendar, calendar_item):
        raise NotImplementedError

