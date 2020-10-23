import base64
import binascii
from email.mime.text import MIMEText

from django.utils.functional import cached_property

from googleapiclient import errors


class GmailMessage:

    def __init__(self, service, message):
        self.service = service
        self._message = message
        self.id = message['id']
        self.threadId = message['threadId']
        self._attachments = []

    @classmethod
    def load(cls, service, message_id):
        message = service.users().messages().get(userId='me', id=message_id).execute()
        return cls(service, message)

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
        return _from[first_position:second_position]

    def body(self, fallback_to_snippet=True, encoding='utf-8'):
        data = None
        if self._message['payload']['mimeType'] in ['multipart/mixed', 'multipart/alternative', 'multipart/related']:
            for part in self._message['payload']['parts']:
                if 'parts' in part:
                    for sub_part in part['parts']:
                        if sub_part['mimeType'] in ['text/plain']:
                            data = sub_part['body']['data']
                            break
                else:
                    if part['mimeType'] in ['text/plain']:
                        data = part['body']['data']
                if data:
                    break
        else:
            for part in self._message['payload']['parts']:
                if part['mimeType'] in ['text/plain']:
                    data = part['body']['data']
                    break
        try:
            return base64.b64decode(data).decode(encoding).strip()
        except binascii.Error:
            if fallback_to_snippet:
                return self._message['snippet']
            raise

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
        raw_message = base64.urlsafe_b64encode(reply_message.as_bytes()).decode('utf-8')

        return self.service.users().messages().send(userId='me', body={
            'raw': raw_message,
            'threadId': self.threadId,
        }).execute()
