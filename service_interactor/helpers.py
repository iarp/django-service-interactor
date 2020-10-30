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
from .providers.google import GoogleServiceProvider

from googleapiclient import errors


def _get_service_from_objs(service):
    if isinstance(service, GoogleServiceProvider):
        service = service.gmail_service
    elif isinstance(service, GmailHelper):
        service = service.service
    return service


class GmailHelper:

    def __init__(self, service):
        self.service = _get_service_from_objs(service)

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

        service = _get_service_from_objs(service)

        message = service.users().messages().get(userId='me', id=message_id).execute()
        return cls(service, message)

    @staticmethod
    def send_new_message(service, to, subject, body, attachments=None, body_type='plain', _from=None):
        service = _get_service_from_objs(service)

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
