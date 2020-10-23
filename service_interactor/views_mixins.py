from django.contrib import messages
from django.shortcuts import redirect

from .models import GoogleServiceProvider, MicrosoftServiceProvider


class AddActiveServiceProvider(object):
    def dispatch(self, request, *args, **kwargs):
        self.provider = request.active_provider
        self.service = request.active_service
        return super().dispatch(request=request, *args, **kwargs)


class RequiresServiceProvider(AddActiveServiceProvider):

    provider_classes = [GoogleServiceProvider, MicrosoftServiceProvider]

    def _get_provider_classes(self):
        if not self.provider_classes:
            raise ValueError(f'{self.__class__.__name__} must supply provider_classes attribute.')
        return self.provider_classes

    def dispatch(self, request, *args, **kwargs):
        pc = self._get_provider_classes()
        if request.active_provider.__class__ not in pc:
            messages.error(request, 'This feature requires a {} account.'.format(
                ' or '.join([p.provider_name for p in pc])
            ))
            return redirect('socialaccount_connections')
        return super().dispatch(request=request, *args, **kwargs)


class RequiresGoogleServiceProvider(RequiresServiceProvider):
    provider_classes = [GoogleServiceProvider]


class RequiresMicrosoftServiceProvider(RequiresServiceProvider):
    provider_classes = [MicrosoftServiceProvider]


class RequiresServiceCalendarAccess(object):

    return_url = 'socialaccount_connections'

    def dispatch(self, request, *args, **kwargs):
        if not request.active_provider.has_calendar_access:
            messages.error(request, 'Calendar Access Required')
            return redirect(self.return_url)
        return super().dispatch(request=request, *args, **kwargs)


class RequiresServiceFilesAccess(object):

    return_url = 'socialaccount_connections'

    def dispatch(self, request, *args, **kwargs):
        if not request.active_provider.has_file_access:
            messages.error(request, 'Files Access Required')
            return redirect(self.return_url)
        return super().dispatch(request=request, *args, **kwargs)
