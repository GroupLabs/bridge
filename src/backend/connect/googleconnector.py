import os
import io
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from datetime import datetime, timedelta, timezone
import base64
from email.mime.text import MIMEText
from dotenv import load_dotenv
import json
import httpx
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.errors import HttpError
import sys
from config import config
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from log import setup_logger

logger = setup_logger("googelconnector")
logger.info("LOGGER READY")

#to do: 
#Connect to an entire organizations workspace, not individual user
#connect to gmail, google notes... all other google apps
#store and autogenerate metadata in ES, link that metadata to actual data using an external ID
#read the metadata upon request

env_path = Path('..') / '.env'
load_dotenv(dotenv_path=env_path)

# Path to your OAuth 2.0 client credentials file
CLIENT_SECRETS_FILE = os.getenv('CLIENT_SECRET_FILE')
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/gmail.readonly'
]

def authenticate():
    # Run local server to get the credentials
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=8080)
    return creds

def build_service(creds):
    # Build the Drive API client
    service = build('drive', 'v3', credentials=creds)
    return service

def build_calendar_service(creds):
    # Build the Calendar API client
    service = build('calendar', 'v3', credentials=creds)
    return service

def build_gmail_service(creds):
    # Build the Gmail API client
    service = build('gmail', 'v1', credentials=creds)
    return service

def list_files(service, created_after=None):
    try:
        created_after = "2024-01-01T00:00:00Z"  # Hardcoded date
        query = f"createdTime > '{created_after}'"
        logger.debug(f"Query: {query}")

        page_token = None
        items = []
        while True:
            logger.debug(f"Fetching files with page token: {page_token}")
            results = service.files().list(
                q=query,
                pageSize=1000,
                fields="nextPageToken, files(id, name, mimeType, createdTime)",
                pageToken=page_token
            ).execute()
            items.extend(results.get('files', []))
            page_token = results.get('nextPageToken', None)
            logger.debug(f"Next page token: {page_token}")
            if not page_token:
                break

        logger.debug(f"Total files retrieved: {len(items)}")
        if not items:
            logger.info('No files found.')
        else:
            logger.info('Files:')
            supported_mime_types = [
                'application/vnd.google-apps.document',  # Google Docs
                'application/vnd.google-apps.spreadsheet',  # Google Sheets
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # Excel files
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # Word files
                'application/pdf',  # PDF files
                'application/vnd.google-apps.presentation',  # Google Slides
                'application/vnd.openxmlformats-officedocument.presentationml.presentation'  # PowerPoint files
            ]
            items = [item for item in items if item['mimeType'] in supported_mime_types]
            for item in items:
                logger.info(f"{item['name']} ({item['id']}) - {item['mimeType']} - Created Time: {item['createdTime']}")
        return items
    except HttpError as e:
        logger.error(f"HTTP error listing files: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"General error listing files: {str(e)}")
        return []

async def stream_file(service, file_id, file_name):
    try:
        file_metadata = service.files().get(fileId=file_id).execute()
        mime_type = file_metadata['mimeType']
        
        if mime_type.startswith('application/vnd.google-apps.'):
            export_mime_type = {
                'application/vnd.google-apps.document': 'application/pdf',
                'application/vnd.google-apps.spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            }.get(mime_type, None)
            
            if export_mime_type:
                request = service.files().export_media(fileId=file_id, mimeType=export_mime_type)
                file_extension = {
                    'application/pdf': '.pdf',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
                    'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx'
                }.get(export_mime_type, '')
                file_name += file_extension
            else:
                logger.error(f"File '{file_name}' cannot be exported because it's not a supported Google Docs editors file.")
                return None, None
        else:
            request = service.files().get_media(fileId=file_id)
        
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            try:
                status, done = downloader.next_chunk()
                logger.info(f"Download {int(status.progress() * 100)}%.")
            except HttpError as e:
                if e.resp.status in [403, 404]:
                    logger.error(f"Error in streaming file '{file_name}': {e}")
                    return None, None
                raise
        
        fh.seek(0)
        return fh, file_name
    except HttpError as e:
        logger.error(f"Error in streaming file '{file_name}': {e}")
        return None, None
    except Exception as e:
        logger.error(f"Error in streaming file '{file_name}': {str(e)}")
        return None, None



async def send_file_to_endpoint(file_stream, file_name, user_id):
    async with httpx.AsyncClient() as client:
        files = {'file': (file_name, file_stream, 'application/octet-stream')}
        data = {'from_source': 'google'}
        response = await client.post(f"http://localhost:8000/load_query/{user_id}", files=files, data=data)
        logger.debug(f"Response from server: {response.text}")
        if response.status_code == 202:
            logger.info(f"File '{file_name}' accepted for loading")
        else:
            logger.warning(f"File '{file_name}' was not accepted for loading. Status code: {response.status_code}")

async def send_data_as_text_file_to_endpoint(data_type, data, user_id):
    async with httpx.AsyncClient() as client:
        if data_type in ['calendar_events', 'received_emails', 'sent_emails']:
            if data_type == 'calendar_events':
                file_content = '\n'.join([f"Event: {event['summary']}, Start: {event['start']}, End: {event['end']}" for event in data])
            else:
                file_content = '\n'.join([f"Email Subject: {email['subject']}, Body: {email['body']}" for email in data])
        else:
            file_content = ''

        file_name = f"{data_type}.txt"
        file_stream = io.BytesIO(file_content.encode('utf-8'))
        files = {'file': (file_name, file_stream, 'text/plain')}
        data = {'from_source': 'google'}
        url = f"http://localhost:8000/load_query/{user_id}"  # Correctly interpolate user_id
        response = await client.post(url, files=files, data=data)
        logger.debug(f"Response from server: {response.text}")
        if response.status_code == 202:
            logger.info(f"{data_type} data accepted for loading")
        else:
            logger.warning(f"{data_type} data was not accepted for loading. Status code: {response.status_code}")


async def download_and_load(creds_json, user_id):
    try:
        creds_dict = json.loads(creds_json)
        
        if 'refresh_token' not in creds_dict:
            raise ValueError("Missing 'refresh_token' field in credentials")
        
        creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
        
        # Calculate the date one month ago
        created_after = (datetime.now() - timedelta(days=30)).isoformat() + 'Z'
        
        # Handle Google Drive files
        drive_service = build_service(creds)
        files = list_files(drive_service, created_after=created_after)
        logger.debug(f"Files found: {files}")

        if files:
            for item in files:
                file_stream, file_name = await stream_file(drive_service, item['id'], item['name'])
                if file_stream and file_name:
                    await send_file_to_endpoint(file_stream, file_name, user_id)
                else:
                    logger.warning(f"Skipping file '{item['name']}' due to export/download issues.")

        # Handle Google Calendar events
        calendar_service = build_calendar_service(creds)
        events = list_calendar_events(calendar_service)
        if events:
            await send_data_as_text_file_to_endpoint('calendar_events', events, user_id)

        # Handle Gmail messages
        gmail_service = build_gmail_service(creds)
        
        # Get the last 10 received emails
        received_messages = list_messages(gmail_service, 'me', ['INBOX'])
        if received_messages:
            received_emails = []
            for msg in received_messages:
                msg_data = get_message(gmail_service, 'me', msg['id'])
                msg_payload = msg_data['payload']
                msg_subject = next(header['value'] for header in msg_payload['headers'] if header['name'] == 'Subject')
                msg_body = get_message_body(msg_payload)
                received_emails.append({"subject": msg_subject, "body": msg_body})
            await send_data_as_text_file_to_endpoint('received_emails', received_emails, user_id)

        # Get the last 10 sent emails
        sent_messages = list_messages(gmail_service, 'me', ['SENT'])
        if sent_messages:
            sent_emails = []
            for msg in sent_messages:
                msg_data = get_message(gmail_service, 'me', msg['id'])
                msg_payload = msg_data['payload']
                msg_subject = next(header['value'] for header in msg_payload['headers'] if header['name'] == 'Subject')
                msg_body = get_message_body(msg_payload)
                sent_emails.append({"subject": msg_subject, "body": msg_body})
            await send_data_as_text_file_to_endpoint('sent_emails', sent_emails, user_id)

        logger.info("Files, events, and emails streamed and sent successfully")
    except Exception as e:
        logger.error(f"Error in downloading and loading files: {str(e)}")

def get_flow():
    return Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, 
        scopes=SCOPES, 
        redirect_uri=config.GOOGLE_REDIRECT_URI
    )
  

def list_calendar_events(service):
    now = datetime.now(timezone.utc).isoformat()  # Use timezone-aware datetime
    week_from_now = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    
    events_result = service.events().list(
        calendarId='primary', timeMin=now, timeMax=week_from_now,
        maxResults=100, singleEvents=True,
        orderBy='startTime').execute()
    
    events = events_result.get('items', [])
    if not events:
        logger.info('No upcoming events found.')
    else:
        logger.info('Upcoming events:')
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            logger.info(f"{event['summary']} - 'start': {start} - 'end': {end}")
    # Structure the events for the API
    structured_events = [{'summary': event['summary'], 'start': event['start'], 'end': event['end']} for event in events]
    return structured_events


def list_messages(service, user_id, label_ids=[], max_results=10):
    results = service.users().messages().list(userId=user_id, labelIds=label_ids, maxResults=max_results).execute()
    messages = results.get('messages', [])
    return messages

def get_message(service, user_id, msg_id):
    msg = service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()
    return msg

def get_message_body(msg_payload):
    msg_body = ''
    if 'data' in msg_payload['body']:
        msg_body = base64.urlsafe_b64decode(msg_payload['body']['data']).decode('utf-8')
    elif 'parts' in msg_payload:
        for part in msg_payload['parts']:
            if part['mimeType'] == 'text/plain':
                msg_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                break
    return msg_body


def print_emails(service, label_id, message_type):
    messages = list_messages(service, 'me', [label_id])
    for msg in messages:
        msg_data = get_message(service, 'me', msg['id'])
        msg_payload = msg_data['payload']
        msg_headers = msg_payload['headers']
        msg_subject = next(header['value'] for header in msg_headers if header['name'] == 'Subject')
        msg_body = ''
        
        if 'data' in msg_payload['body']:
            msg_body = base64.urlsafe_b64decode(msg_payload['body']['data']).decode('utf-8')
        elif 'parts' in msg_payload:
            for part in msg_payload['parts']:
                if part['mimeType'] == 'text/plain':
                    msg_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    break
        
        msg_body_excerpt = ' '.join(msg_body.split()[:10]) + '...'
        print(f"{message_type} - {msg_subject} - {msg_body_excerpt}")

# Example usage
if __name__ == '__main__':
    creds = authenticate()
    service = build_service(creds)
    calendar_service = build_calendar_service(creds)
    gmail_service = build_gmail_service(creds)

    print("Listing all files in Google Drive:")
    files = list_files(service)
    for file in files:
        print(f"{file['name']} ({file['id']}) - {file['mimeType']}")

    #file_name_to_download = input("Enter the name of the file to download: ")
    #download_file(service, file_name_to_download)

    print("\nListing upcoming events in Google Calendar for the next week:")
    list_calendar_events(calendar_service)

    print("\nListing last 10 emails received:")
    print_emails(gmail_service, 'INBOX', 'Received')

    print("\nListing last 10 emails sent:")
    print_emails(gmail_service, 'SENT', 'Sent')