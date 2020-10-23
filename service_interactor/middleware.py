from collections import OrderedDict

from django.db.models import QuerySet

from .models import Service
from .providers.base import ServiceProvider
from .providers import GoogleServiceProvider


class ServiceRegistry:

    def __init__(self, services=None):
        self._ids = set()
        self._service_provider_map = OrderedDict()
        self.services = []
        self.providers = []

        if isinstance(services, QuerySet):
            for serv in services:
                self.register(serv)

    def register(self, service: Service, provider=None):
        if not provider:
            provider = service.get_service_provider()  # type: GoogleServiceProvider

        self._ids.add(service.id)
        self.services.append(service)
        self.providers.append(provider)

        self._service_provider_map[service.id] = {
            'service': service,
            'provider': provider
        }

    def __len__(self):
        return len(self._service_provider_map)

    def __getitem__(self, item):
        return self.services[item], self.providers[item]

    def __contains__(self, item):
        if isinstance(item, int):
            return item in self._ids
        if issubclass(type(item), ServiceProvider):
            return item in self.providers
        return item in self.services

    def get_service(self, service_id):
        return self._service_provider_map[service_id]['service']

    def get_provider(self, service_id):
        return self._service_provider_map[service_id]['provider']

    @property
    def enabled(self):
        items = ServiceRegistry()
        for sic, data in self._service_provider_map.items():
            if data['provider'] and data['provider'].is_enabled:
                items.register(service=data['service'], provider=data['provider'])
        return items


class AddServiceProviderObjects(object):

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        if not request.user.is_authenticated:
            return self.get_response(request)

        request.service_accounts = ServiceRegistry()

        for service in request.user.service_set.filter():
            request.service_accounts.register(service)

        new_service_id = request.GET.get('service_id') or None
        if new_service_id:
            try:
                new_service_id = int(new_service_id)
                if new_service_id in request.service_accounts:
                    request.session['active_service_provider_id'] = new_service_id
            except (TypeError, ValueError):
                new_service_id = None

        active_spi = new_service_id or request.session.get('active_service_provider_id')

        if active_spi and active_spi in request.service_accounts:
            request.active_service = request.service_accounts.get_service(active_spi)
            request.active_provider = request.service_accounts.get_provider(active_spi)

        else:
            for service, provider in request.service_accounts.enabled:
                request.active_service = service
                request.active_provider = provider
                request.session['active_service_provider_id'] = service.pk
                break
            else:
                request.active_service = None
                request.active_provider = None

        return self.get_response(request)
