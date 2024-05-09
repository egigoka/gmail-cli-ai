import os
import pickle
import base64

try:
    from google.auth.transport.requests import Request
except ModuleNotFoundError:
    print("install google-api-python-client")
    exit(1)

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


def gmail_authenticate(gmail_secrets_file, scopes):
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                gmail_secrets_file, scopes)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)


def archive_email(service, user_id, email_id):
    # Remove the email from the INBOX label
    service.users().messages().modify(userId=user_id, id=email_id,
                                      body={'removeLabelIds': ['INBOX']}).execute()


def add_label_to_email(service, user_id, email_id, label_id):
    # Add a label to the email
    service.users().messages().modify(userId=user_id, id=email_id,
                                      body={'addLabelIds': [label_id]}).execute()


def list_emails(service, user_id='me', label_ids=None, max_results=10):
    if label_ids is None:
        label_ids = ['INBOX']

    messages = []
    page_token = None
    while True:
        results = service.users().messages().list(userId=user_id,
                                                  labelIds=label_ids,
                                                  maxResults=max_results,
                                                  pageToken=page_token).execute()
        messages.extend(results.get('messages', []))
        page_token = results.get('nextPageToken')

        if not page_token:
            break

    return messages


def get_email(service, user_id, email_id):
    # Fetch the email by ID
    email = service.users().messages().get(userId=user_id, id=email_id, format='full').execute()
    return email


def mark_as_spam(gmail_auth, user_id, email_id):
    add_label_to_email(gmail_auth, user_id, email_id, 'SPAM')


def get_email_headers(email):
    headers = {}
    for header in email['payload']['headers']:
        headers[header['name']] = header['value']

    return headers


def get_email_body(email):
    # Check if the email is multipart
    if 'parts' in email['payload']:
        body = ""
        for part in email['payload']['parts']:
            if 'data' in part['body']:
                body += part['body']['data']
                break
    else:
        # If not multipart, just get the whole body
        body = email['payload']['body']['data']

    # Decode the email body
    body = base64.urlsafe_b64decode(body.encode('ASCII')).decode('utf-8')
    return body


def get_email_attachments_metadata(message):
    parts = message.get('payload').get('parts', [])
    attachments = []

    for part in parts:
        if part['filename']:
            attachments.append({
                'filename': part['filename'],
                'mimeType': part['mimeType']
            })

    return attachments


def get_equal_substrings_from_begging_center_end(string, total_length):
    if len(string) < total_length:
        return string

    sep = "!!!ATTENTION: THIS IS A SEPARATOR BETWEEN CUT CONTENT!!!"

    substrings_length = int((total_length - len(sep) * 2) / 3)

    center_index = int(len(string) / 2 - substrings_length / 2)

    substrings = [string[:substrings_length],
                  string[center_index:center_index + substrings_length],
                  string[-substrings_length:]]

    return sep.join(substrings)


def mark_email_as_useful(useful_emails, email_id):
    useful_emails.append(email_id)
    useful_emails.save()


def get_labels(service, user_id):
    response = service.users().labels().list(userId=user_id).execute()
    labels = response.get('labels', [])
    return {label['name'].lower(): label['id'] for label in labels}
