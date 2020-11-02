Django Service Interactor
=========================


Installation
============

Install from repo::

    pip install -e git+https://github.com/iarp/django-service-interactor.git#egg=django_service_interactor
    pip install -e git+http://192.168.2.3:3000/iarp/django-service-interactor.git#egg=django_service_interactor

settings.py::

    INSTALLED_APPS = [
        ...
        'service_interactor',
        ...
    ]

Usage
=====

    from allauth.socialaccount.models import SocialAccount
    from service_interactor.providers.google import GoogleServiceProvider
    
    account = SocialAccount.objects.get(id=1, provider='google')
    gsp = GoogleServiceProvider(account=account)
