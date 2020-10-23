from __future__ import unicode_literals

from allauth.socialaccount.providers.microsoft.provider import (
    MicrosoftGraphProvider,
)
from allauth.socialaccount.providers.microsoft.views import (
    MicrosoftGraphOAuth2Adapter,
)
from allauth.socialaccount.providers.oauth2.views import (
    OAuth2CallbackView,
    OAuth2LoginView,
)


class MicrosoftGraphOAuth2AdapterCustom(MicrosoftGraphOAuth2Adapter):
    provider_id = MicrosoftGraphProvider.id

    def complete_login(self, request, app, token, **kwargs):

        # This is the only time in the system that I can obtain the scopes returned by the token authorization.
        request.session['scopes_received'] = kwargs.get('response', {}).get('scope', '').split(' ')

        return super().complete_login(request, app, token, **kwargs)


oauth2_login = OAuth2LoginView.adapter_view(MicrosoftGraphOAuth2AdapterCustom)
oauth2_callback = OAuth2CallbackView.adapter_view(MicrosoftGraphOAuth2AdapterCustom)
