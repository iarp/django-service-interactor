import logging

from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save

from allauth.socialaccount.signals import (
    pre_social_login,
    social_account_added,
)

from .models import Scope, Service, UserProviderScope


log = logging.getLogger('service_interactor.signals')


def setup_user_scopes(sociallogin, **kwargs):
    s, _ = Service.objects.get_or_create(
        account=sociallogin.account,
        user=sociallogin.user
    )
    sp = s.get_service_provider()
    if sp:
        sp.setup_default_scopes()


social_account_added.connect(setup_user_scopes)


def ensure_default_scopes_exist(**kwargs):
    user = kwargs.get('instance') or kwargs.get('user')  # type: User
    for account in user.socialaccount_set.all():
        s, _ = Service.objects.get_or_create(
            account=account,
            user=user
        )
        sp = s.get_service_provider()
        if sp:
            sp.setup_default_scopes()


user_logged_in.connect(ensure_default_scopes_exist)
post_save.connect(ensure_default_scopes_exist, sender=User)


def copy_default_scopes(request, sociallogin, **kwargs):

    if not sociallogin.user.id:
        return

    scopes_received = request.GET.get('scope', '').split()

    # Microsoft provider was overridden and scopes stored in session.
    if not scopes_received:
        scopes_received = request.session.get('scopes_received')

    if not scopes_received:
        return

    for scope in scopes_received:

        if sociallogin.account.provider == 'google':
            if scope == 'email':
                scope = 'https://www.googleapis.com/auth/userinfo.email'
            elif scope == 'profile':
                scope = 'https://www.googleapis.com/auth/userinfo.profile'

        scope, _ = Scope.objects.get_or_create(provider=sociallogin.account.provider, name=scope)

        ups, created = UserProviderScope.objects.get_or_create(account=sociallogin.account, scope=scope)

        if created:
            message = None
            if scope.access_type == 'calendar' and scope.grants_access:
                message = 'Calendar'
            elif scope.access_type == 'files' and scope.grants_access:
                message = 'Files'
            if message:
                messages.success(request, f'Successfully granted access to {message}')


pre_social_login.connect(copy_default_scopes)
