import pytz
import dateutil.parser
import io

from django.utils.functional import cached_property
from django.utils import timezone

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from .base import ServiceProvider
from .. import service_objects
from ..helpers import GmailHelper, YouTubeHelper


class GoogleServiceProvider(ServiceProvider):
    provider_id = 'google'
    provider_name = 'Google'

    primary_email_domains = ['gmail.com', 'googlemail.com', 'google.com']

    requires_token_secret = True
    token_uri = 'https://accounts.google.com/o/oauth2/token'

    def resource(self, service_name, version='v3'):
        return build(service_name, version, credentials=self.credentials)

    @cached_property
    def calendar_service(self):
        return self.resource(service_name='calendar', version='v3')

    @cached_property
    def sheets_service(self):
        return self.resource(service_name='sheets', version='v4')

    @cached_property
    def drive_service(self):
        return self.resource(service_name='drive', version='v3')

    @cached_property
    def gmail_service(self):
        return self.resource(service_name='gmail', version='v1')

    @cached_property
    def youtube_service(self):
        return self.resource(service_name='youtube', version='v3')

    def get_files(self, **kwargs):
        """ Obtain all of the users Drive files. Yields results as it queries data.

        References:
            https://developers.google.com/drive/api/v3/reference/files/list

        Args:
            **kwargs: see references

        Returns:
            Yields a dict for a single file
        """
        while True:
            files_resource = self.drive_service.files().list(**kwargs).execute()

            next_page_token = files_resource.get('nextPageToken')

            for file in files_resource.get('files', []):
                yield file

            if next_page_token:
                kwargs['pageToken'] = next_page_token
            else:
                break

    def download_google_doc_file(self, file_id, mime_type):
        """ Downloads a specific Google Document file by ID from the users Google Drive. Maximum 10MB in size.

        References:
             https://developers.google.com/drive/api/v3/reference/files/export

        Args:
            file_id: File ID to download
            mime_type: mimeType expected

        Returns:
            File handle for the file in memory
        """
        media = self.drive_service.files().export_media(fileId=file_id, mimeType=mime_type)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, media)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            # print(f'Download {status.progress() * 100}%')
        fh.seek(0)
        return fh

    def download_file(self, file_id):
        """ Downloads a specific file by ID from the users Google Drive.

        References:
             https://developers.google.com/drive/api/v3/reference/files/export
             https://developers.google.com/drive/api/v3/manage-downloads#downloading_a_file

        Args:
            file_id: File ID to download

        Returns:
            File handle for the file in memory
        """
        media = self.drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, media)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            # print(f'Download {status.progress() * 100}%')
        fh.seek(0)
        return fh

    def get_file_details(self, file_id, **kwargs):
        """ Obtain a specific file's information, see ref below for available fields

        References:
            https://developers.google.com/drive/api/v3/reference/files#resource

        Args:
            file_id:
            **kwargs:

        Returns:

        """
        return self.drive_service.files().get(fileId=file_id, **kwargs).execute()

    def get_folders(self, name=None):
        q = 'mimeType="application/vnd.google-apps.folder" and trashed = false'
        if name:
            q = f'{q} and name = "{name}"'
        return self.get_files(q=q)

    def get_or_create_folder(self, name):
        # Get or create the folder
        for folder in self.get_folders(name=name):
            return folder
        else:
            folder_metadata = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
            return self.drive_service.files().create(body=folder_metadata).execute()

    def get_calendars(self):
        items = self.calendar_service.calendarList().list().execute()
        for calendar in items.get('items', []):
            yield service_objects.Calendar(
                id=calendar['id'],
                name=calendar['summary'],
                primary=calendar.get('primary') or None,
                raw=calendar,
            )

    def get_calendar_events(self, calendar_id, *args, **kwargs):
        """

            self.get_events(timeMin=now, maxResults=10, singleEvents=True, orderBy='startTime')

            # Call the Calendar API
            now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
            print('Getting the upcoming 10 events')

            cal = Calendar.objects.get(user=u, primary=True)
            for event in cal.get_events(timeMin=now, maxResults=10, singleEvents=True, orderBy='startTime'):
                print(event)

        """
        # TODO: Needs more work on the dict idea
        items = self.calendar_service.events().list(calendarId=calendar_id, *args, **kwargs).execute()
        for item in items.get('items', []):
            yield service_objects.CalendarEvent(
                id=item['id'],
                calendar_id=calendar_id,
                link=item['htmlLink'],
                name=item['summary'],
                location=item['location'],
                description=item['description'],
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
            'summary': event.summary,
            'location': event.location,
            'description': event.description,
            'start': {
                'dateTime': event.start.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': event.end.isoformat(),
                'timeZone': 'UTC',
            },
        }

    def create_calendar_event(self, calendar, calendar_item):
        body = self.format_calendaritem_details(event=calendar_item)
        event = self.calendar_service.events().insert(
            calendarId=calendar.calendar_id,
            body=body
        ).execute()
        return service_objects.CalendarEvent(
            id=event['id'],
            calendar_id=calendar.calendar_id,
            link=event['htmlLink'],
            raw=event
        )

    def delete_calendar_event(self, calendar, calendar_item):
        return self.calendar_service.events().delete(
            calendarId=calendar.calendar_id,
            eventId=calendar_item.event_id,
        ).execute()

    def get_gmail_helper(self):
        return GmailHelper(self)

    def get_youtube_helper(self):
        return YouTubeHelper(self)
