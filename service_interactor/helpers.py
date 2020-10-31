import base64
import binascii
import email
import mimetypes
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase

from django.utils.functional import cached_property

from googleapiclient import errors


def _get_service_from_objs(service, _type):

    val = getattr(service, f'{_type}_service', None)
    if val:
        return val

    return service.service


class GmailHelper:

    def __init__(self, service):
        self.service = _get_service_from_objs(service, 'gmail')

    def messages(self, max_results=None, page_token=None, q=None, label_ids=None, include_spam_trash=None):
        vals = {
            'userId': 'me',
        }
        if max_results:
            vals['maxResults'] = max_results
        if page_token:
            vals['pageToken'] = page_token
        if q:
            vals['q'] = q
        if label_ids:
            vals['labelIds'] = label_ids
        if include_spam_trash is not None:
            vals['includeSpamTrash'] = include_spam_trash

        while True:

            data = self.service.users().messages().list(**vals).execute()

            vals['pageToken'] = data.get('nextPageToken')

            for item in data['messages']:
                yield item

            if not vals['pageToken']:
                break

    def labels(self):
        return self.service.users().labels().list(userId='me').execute()

    def create_label(self, name):
        return self.service.users().labels().create(userId='me', body={
            'name': name
        }).execute()

    def send_new_message(self, *args, **kwargs):
        kwargs['service'] = self.service
        return GmailMessage.send_new_message(*args, **kwargs)


class GmailMessage:

    def __init__(self, service, message):
        self.service = service
        self._message = message
        self.id = message['id']
        self.threadId = message['threadId']
        self._attachments = []
        self._body = None

    @classmethod
    def load(cls, service, message_id):

        if isinstance(message_id, dict):
            message_id = message_id['id']

        service = _get_service_from_objs(service, 'gmail')

        message = service.users().messages().get(userId='me', id=message_id).execute()
        return cls(service, message)

    @staticmethod
    def send_new_message(service, to, subject, body, attachments=None, body_type='plain', _from=None):
        service = _get_service_from_objs(service, 'gmail')

        message = MIMEMultipart()
        message['to'] = to
        message['subject'] = subject

        if _from:
            message['from'] = _from

        msg = MIMEText(body, body_type)
        message.attach(msg)

        if not attachments:
            attachments = []
        if not isinstance(attachments, (list, tuple, set)):
            attachments = [attachments]

        for att in attachments:

            content_type, encoding = mimetypes.guess_type(att)
            if content_type is None or encoding is not None:
                content_type = 'application/octet-stream'
            main_type, sub_type = content_type.split('/', 1)

            with open(att, 'rb') as fo:
                if main_type == 'text':
                    msg = MIMEText(fo.read(), _subtype=sub_type)
                elif main_type == 'image':
                    msg = MIMEImage(fo.read(), _subtype=sub_type)
                elif main_type == 'audio':
                    msg = MIMEAudio(fo.read(), _subtype=sub_type)
                else:
                    msg = MIMEBase(main_type, sub_type)
                    msg.set_payload(fo.read())

            if msg:
                msg.add_header('Content-Disposition', 'attachment', filename=os.path.basename(att))
                message.attach(msg)

        msg_as_str = message.as_bytes()
        data = {'raw': base64.urlsafe_b64encode(msg_as_str).decode()}
        output = service.users().messages().send(userId='me', body=data).execute()
        return output

    def get_raw_message(self):
        message = self.service.users().messages().get(userId='me', id=self.id, format='raw').execute()
        return base64.urlsafe_b64decode(message['raw'].encode('utf-8'))

    @cached_property
    def account_email_address(self):
        return self.service.users().getProfile(userId='me').execute()['emailAddress']

    @cached_property
    def headers(self):
        headers = {}
        for header in self._message['payload']['headers']:
            headers[header['name']] = header['value']
        return headers

    @cached_property
    def subject(self):
        return self.headers['Subject']

    @cached_property
    def from_name(self):
        _from = self.headers['From']
        first_position = _from.find('<')
        return _from[:first_position]

    @cached_property
    def from_email(self):
        _from = self.headers['From']
        first_position = _from.find('<') + 1
        second_position = _from.rfind('>', first_position)
        if second_position:
            return _from[first_position:second_position]
        return _from[first_position:]

    def body(self, body_load_order=None):
        if not self._body:
            raw_message = self.get_raw_message()
            email_data = email.message_from_bytes(raw_message, policy=email.policy.default)
            self._body = email_data.get_body(preferencelist=body_load_order or ('plain', 'html'))
            if self._body:
                self._body = self._body.get_content()
        return self._body

    def attachments(self, encoding='utf-8'):
        if self._attachments:
            return self._attachments
        for part in self._message['payload']['parts']:
            if part['filename']:
                data = part.get('body', {}).get('data')
                if not data:
                    try:
                        data = self.service.users().messages().attachments().get(
                            userId='me',
                            messageId=self._message['id'],
                            id=part['body']['attachmentId'],
                        ).execute()['data']
                    except errors.HttpError as error:
                        print('Failed to download attachment: %s' % error)
                        continue

                try:
                    file_data = base64.urlsafe_b64decode(data.encode(encoding))
                except binascii.Error:
                    print('Failed to decode/encode attachment data')
                    continue

                self._attachments.append({
                    'name': part['filename'],
                    'data': file_data,
                })

                # with open(path, 'wb') as f:
                #     f.write(file_data)

        return self._attachments

    def labels(self):
        return self._message['labelIds']

    def label_manager(self, label_ids=None, remove_ids=None, remove_from_inbox=True, mark_as_read=False):
        """ Adds and Remove supplied label ID's

        Args:
            label_ids: list of label ID's to add
            remove_ids: list of label ID's to remove
            remove_from_inbox: Removes INBOX label id
            mark_as_read: Removes UNREAD label id
        """
        if isinstance(remove_ids, str):
            remove_ids = [remove_ids]
        if not isinstance(remove_ids, list):
            remove_ids = []

        if isinstance(label_ids, str):
            label_ids = [label_ids]
        if not isinstance(label_ids, list):
            label_ids = []

        if mark_as_read:
            remove_ids.append('UNREAD')
        if remove_from_inbox:
            remove_ids.append('INBOX')

        return self.service.users().messages().modify(userId='me', id=self._message['id'], body={
            'removeLabelIds': remove_ids, 'addLabelIds': label_ids
        }).execute()

    def reply(self, body):
        """ Replies to this message thread

        Args:
            body: The body of the reply email. It's up to you to
                    include the original email text if you want it.
        """
        reply_message = MIMEText(body)
        reply_message['to'] = self.from_email
        reply_message['from'] = self.account_email_address
        reply_message['subject'] = f"Re: {self.subject}"
        if 'References' in self.headers:
            reply_message['References'] = self.headers['References']
        reply_message['In-Reply-To'] = self.headers['Message-ID']
        raw_message = base64.urlsafe_b64encode(reply_message.as_bytes()).decode('utf-8')

        return self.service.users().messages().send(userId='me', body={
            'raw': raw_message,
            'threadId': self.threadId,
        }).execute()

    def delete(self):
        return self.service.users().messages().trash(userId='me', id=self._message['id']).execute()


class Playlist:

    part = 'snippet,contentDetails,status'

    def __init__(self, service, title, description=None, status='unlisted', playlist_id=None, playlist_data=None):
        self.service = service
        self.id = playlist_id
        self.data = playlist_data

        self.title = title
        self.description = description
        self.status = status

    def __str__(self):
        return f'<Playlist: {self.title}>'

    def __getitem__(self, item):
        return self.data[item]

    @classmethod
    def load_from_response(cls, service, data):
        assert data['kind'] == 'youtube#playlist'
        return cls(
            service=service,
            title=data['snippet']['title'],
            description=data['snippet']['description'],
            status=data['status']['privacyStatus'],
            playlist_id=data['id'],
            playlist_data=data
        )

    def videos(self, page_token=''):
        while True:

            data = self.service.playlistItems().list(
                part='snippet,contentDetails,status',
                playlistId=self.id,
                pageToken=page_token,
            ).execute()

            page_token = data.get('nextPageToken')

            for item in data['items']:
                yield PlaylistItem.load_from_response(self.service, item)

            if not page_token:
                break

    def new_video(self, video_id, **kwargs):
        pi = PlaylistItem(
            service=self.service,
            video_id=video_id,
            playlist_id=self.id,
            **kwargs
        )
        pi.save()
        return pi

    def save(self):
        if self.id:
            return self.update()
        return self.insert()

    def insert(self):
        body = {
            "snippet": {
                "title": self.title,
                "description": self.description,
                "defaultLanguage": "en"
            },
            "status": {
                "privacyStatus": self.status
            }
        }
        data = self.service.playlists().insert(part=self.part, body=body).execute()
        return Playlist.load_from_response(self.service, data)

    def update(self):
        self.data = self.service.playlists().update(
            part=self.part,
            body={
                "id": self.id,
                "snippet": {
                    "title": self.title,
                    "description": self.description,
                },
                "status": {
                    "privacyStatus": self.status
                }
            }
        ).execute()
        return self

    def delete(self):
        return self.service.playlists().delete(id=self.id).execute()


class PlaylistItem:

    part = 'contentDetails,id,snippet,status'

    def __init__(self, service, title=None, description=None, status=None, video_id=None, position=0,
                 playlist_id=None, playlist_item_id=None, playlist_item_data=None):
        self.service = service
        self.title = title
        self.description = description
        self.status = status
        self.video_id = video_id

        self.id = playlist_item_id
        self.data = playlist_item_data
        self.playlist_id = playlist_id
        self.position = position

    def __str__(self):
        return f'<PlaylistItem: {self.video_id} {self.title}>'

    def __getitem__(self, item):
        return self.data[item]

    @classmethod
    def load_from_response(cls, service, data):
        assert data['kind'] == 'youtube#playlistItem'
        return cls(
            service=service,
            title=data['snippet']['title'],
            description=data['snippet']['description'],
            status=data['status']['privacyStatus'],
            video_id=data['contentDetails']['videoId'],
            playlist_id=data['snippet']['playlistId'],
            position=data['snippet']['position'],
            playlist_item_id=data['id'],
            playlist_item_data=data
        )

    def save(self):
        if self.id:
            return self.update()
        return self.insert()

    def insert(self):
        # https://developers.google.com/youtube/v3/docs/playlistItems/insert
        data = self.service.playlistItems().insert(
            part=self.part,
            body={
                "snippet": {
                    "playlistId": self.playlist_id,
                    "position": self.position,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": self.video_id
                    }
                }
            }
        ).execute()
        return PlaylistItem.load_from_response(self.service, data)

    def update(self):
        # https://developers.google.com/youtube/v3/docs/playlistItems/update
        return self.service.playlistItems().update(
            part=self.part,
            body={
                "id": self.id,
                "snippet": {
                    "playlistId": self.playlist_id,
                    "position": self.position,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": self.video_id
                    }
                }
            }
        ).execute()

    def delete(self):
        # https://developers.google.com/youtube/v3/docs/playlistItems/delete
        return self.service.playlistItems().delete(id=self.id).execute()


class YouTubeHelper:

    def __init__(self, service):
        self.service = _get_service_from_objs(service, 'youtube')

    def playlists(self, max_results=25, page_token='', playlist_id=None, channel_id=None):
        # https://developers.google.com/youtube/v3/docs/playlists/list

        vals = {
            'part': 'snippet,contentDetails,player,status',
            'maxResults': max_results,
            'pageToken': page_token
        }

        if playlist_id:
            vals['id'] = playlist_id
        elif channel_id:
            vals['channelId'] = channel_id
        else:
            vals['mine'] = True

        while True:

            data = self.service.playlists().list(**vals).execute()

            vals['pageToken'] = data.get('nextPageToken')

            for item in data['items']:
                playlist = Playlist.load_from_response(self.service, item)
                if playlist_id:
                    return playlist
                yield playlist

            if not vals['pageToken']:
                break

    def new_playlist(self, title, **kwargs):
        return Playlist(service=self.service, title=title, **kwargs).insert()

    def subscriptions(self, page_token=''):
        # https://developers.google.com/youtube/v3/docs/subscriptions/list

        while True:

            data = self.service.subscriptions().list(
                part='snippet,contentDetails,id,subscriberSnippet',
                mine=True,
                pageToken=page_token,
            ).execute()

            page_token = data.get('nextPageToken')

            for item in data['items']:
                yield item

            if not page_token:
                break

    def new_subscription(self, channel_id):
        # https://developers.google.com/youtube/v3/docs/subscriptions/insert
        return self.service.subscriptions().insert(
            part='contentDetails,id,snippet,subscriberSnippet',
            body={
                "snippet": {
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": channel_id
                    }
                }
            }
        ).execute()
