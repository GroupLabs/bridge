import os
import io
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from datetime import datetime, timedelta, timezone
import base64
from email.mime.text import MIMEText
from dotenv import load_dotenv
from log import setup_logger
import json
import httpx
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.errors import HttpError

logger = setup_logger("googelconnector")
logger.info("LOGGER READY")

#to do: 
#Connect to an entire organizations workspace, not individual user
#connect to gmail, google notes... all other google apps
#store and autogenerate metadata in ES, link that metadata to actual data using an external ID
#read the metadata upon request

load_dotenv()

# Path to your OAuth 2.0 client credentials file
CLIENT_SECRETS_FILE = os.getenv('CLIENT_SECRET_FILE')
SCOPES = [
    'https://www.googleapis.com/auth/drive',
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

def list_files(service):
    try:
        results = service.files().list(pageSize=1000, fields="files(id, name, mimeType)").execute()
        items = results.get('files', [])
        if not items:
            logger.info('No files found.')
        else:
            logger.info('Files:')
            for item in items:
                logger.info(f"{item['name']} ({item['id']}) - {item['mimeType']}")
        return items
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
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
            }.get(mime_type, 'application/pdf')
            
            request = service.files().export_media(fileId=file_id, mimeType=export_mime_type)
            file_extension = {
                'application/pdf': '.pdf',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx'
            }.get(export_mime_type, '.pdf')
            
            file_name += file_extension
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


async def send_file_to_endpoint(file_stream, file_name):
    async with httpx.AsyncClient() as client:
        files = {'file': (file_name, file_stream, 'application/octet-stream')}
        response = await client.post("http://localhost:8000/load_query", files=files)
        logger.debug(f"Response from server: {response.text}")
        if response.status_code == 202:
            logger.info(f"File '{file_name}' accepted for loading")
        else:
            logger.warning(f"File '{file_name}' was not accepted for loading. Status code: {response.status_code}")

async def download_and_load(creds_json):
    try:
        creds_dict = json.loads(creds_json)
        
        if 'refresh_token' not in creds_dict:
            raise ValueError("Missing 'refresh_token' field in credentials")
        
        creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
        service = build_service(creds)
        items = list_files(service)
        logger.debug(f"Files found: {items}")

        if not items:
            logger.info("No files found.")
        else:
            for item in items:
                file_stream, file_name = await stream_file(service, item['id'], item['name'])
                if file_stream and file_name:
                    await send_file_to_endpoint(file_stream, file_name)
            logger.info("Files streamed and sent successfully")
    except Exception as e:
        logger.error(f"Error in downloading and loading files: {str(e)}")

REDIRECT_URI = 'http://localhost:8000/oauth2callback'

def get_flow():
    return Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
  

def list_calendar_events(service):
    now = datetime.now(timezone.utc).isoformat()  # Use timezone-aware datetime
    week_from_now = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    
    events_result = service.events().list(
        calendarId='primary', timeMin=now, timeMax=week_from_now,
        maxResults=100, singleEvents=True,
        orderBy='startTime').execute()
    
    events = events_result.get('items', [])
    if not events:
        print('No upcoming events found.')
    else:
        print('Upcoming events:')
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            print(f"{event['summary']} - 'start': {start} - 'end': {end}")

def list_messages(service, user_id, label_ids=[], max_results=10):
    results = service.users().messages().list(userId=user_id, labelIds=label_ids, maxResults=max_results).execute()
    messages = results.get('messages', [])
    return messages

def get_message(service, user_id, msg_id):
    msg = service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()
    return msg

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
    list_files(service)

    #file_name_to_download = input("Enter the name of the file to download: ")
    #download_file(service, file_name_to_download)

    print("\nListing upcoming events in Google Calendar for the next week:")
    list_calendar_events(calendar_service)

    print("\nListing last 10 emails received:")
    print_emails(gmail_service, 'INBOX', 'Received')

    print("\nListing last 10 emails sent:")
    print_emails(gmail_service, 'SENT', 'Sent')