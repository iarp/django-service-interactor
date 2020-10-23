import dateutil.parser
import pytz
import requests

from django.utils import timezone

from .. import service_objects
from .base import ServiceProvider


class MicrosoftServiceProvider(ServiceProvider):
    provider_id = 'microsoft'
    provider_name = 'Microsoft'

    primary_email_domains = ['live.ca', 'live.com', 'hotmail.com', 'outlook.com', 'msn.com', 'msn.net']

    graph_url = 'https://graph.microsoft.com/v1.0'
    token_uri = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'

    def get_email(self):
        return self.account.extra_data.get('userPrincipalName')

    def send_request(self, url, method='GET', **kwargs):
        headers = kwargs.pop('headers', {})
        if not headers:
            kwargs['headers'] = {}
        kwargs['headers']['Authorization'] = self.credentials.token
        r = requests.request(
            method=method,
            url=f'{self.graph_url}{url}',
            **kwargs
        )
        if method in ['DELETE']:
            return
        output = r.json()
        if 'error' in output:
            print(r.text)
        return r.json()

    def get_calendars(self):
        items = self.send_request('/me/calendars')
        for item in items.get('value'):
            yield service_objects.Calendar(
                id=item['id'],
                name=item['name'],
                can_edit=item['canEdit'],
                primary=item['name'] == 'Calendar' or None,
                raw=item,
            )

    def get_calendar_events(self, **kwargs):
        items = self.send_request('/me/events')
        for item in items.get('value'):
            yield service_objects.CalendarEvent(
                id=item['id'],
                calendar_id=item['iCalUId'],
                name=item['subject'],
                link=item['webLink'],
                location=item.get('location').get('displayName', ''),
                description=item['webLink'],
                start=timezone.make_aware(
                    dateutil.parser.parse(item['start']['dateTime']),
                    pytz.timezone(item['start']['timeZone'])
                ),
                end=timezone.make_aware(
                    dateutil.parser.parse(item['end']['dateTime']),
                    pytz.timezone(item['end']['timeZone'])
                ),
                raw=item,
            )

    @staticmethod
    def format_calendaritem_details(event):
        return {
            'subject': event.summary,
            'body': {
                'content': event.description,
                'contentType': 'text'
            },
            'start': {
                'dateTime': event.start.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': timezone.get_current_timezone_name()
            },
            'end': {
                'dateTime': event.end.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': timezone.get_current_timezone_name()
            },
            'location': {
                'displayName': event.location
            },
        }

    def create_calendar_event(self, calendar, calendar_item):
        data = self.send_request(
            f'/me/calendars/{calendar.calendar_id}/events',
            method='POST',
            json=self.format_calendaritem_details(calendar_item)
        )
        return service_objects.CalendarEvent(
            id=data['id'],
            calendar_id=data['iCalUId'],
            link=data['webLink'],
            raw=data
        )

    def delete_calendar_event(self, calendar, calendar_item):
        return self.send_request(
            f'/me/calendars/{calendar.calendar_id}/events/{calendar_item.event_id}',
            method='DELETE'
        )
