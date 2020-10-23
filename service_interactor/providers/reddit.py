import requests
from requests.auth import HTTPBasicAuth
from google.auth.transport.requests import Request

from django.utils import timezone

from .base import ServiceProvider


class RedditServiceProvider(ServiceProvider):
    provider_id = 'reddit'
    provider_name = 'Reddit'

    token_uri = 'https://www.reddit.com/api/v1/access_token'

    def __init__(self, *args, user_agent, **kwargs):
        self.user_agent = user_agent
        super(RedditServiceProvider, self).__init__(*args, **kwargs)

    def _refresh_token(self, credentials):
        print('Refreshing', self.account, self.account.provider)

        with requests.Session() as session:
            session.headers = {
                'User-Agent': self.user_agent,
                'Authorization': f'Bearer {credentials.client_secret}',
            }
            session.auth = HTTPBasicAuth(credentials.client_id, credentials.client_secret)
            req = Request(session)
            credentials.refresh(req)

        if credentials.expiry:
            self.token.expires_at = timezone.make_aware(credentials.expiry)

        if credentials.refresh_token:
            self.token.token_secret = credentials.refresh_token

        self.token.token = credentials.token

        self.token.save()
