import os
import io
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Path to your OAuth 2.0 client credentials file
CLIENT_SECRETS_FILE = 'client_secret_324332669662-3gvuu44796go6v2t3lukejgjn350rpiu.apps.googleusercontent.com.json'
SCOPES = ['https://www.googleapis.com/auth/drive']

SCOPES = ['https://www.googleapis.com/auth/drive']

def authenticate():
    # Run local server to get the credentials
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=8080)
    return creds

def build_service(creds):
    # Build the Drive API client
    service = build('drive', 'v3', credentials=creds)
    return service

def list_files(service):
    results = service.files().list(pageSize=100, fields="files(id, name, mimeType)").execute()
    items = results.get('files', [])
    if not items:
        print('No files found.')
    else:
        print('Files:')
        for item in items:
            print(f"{item['name']} ({item['id']}) - {item['mimeType']}")
    return items

def download_file(service, file_name):
    files = list_files(service)
    file_id = None
    mime_type = None
    for file in files:
        if file['name'] == file_name:
            file_id = file['id']
            mime_type = file['mimeType']
            break
    if file_id:
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
        fh = io.FileIO(file_name, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%.")
        print(f"File downloaded as {file_name}")
    else:
        print(f"File named {file_name} not found.")

# Example usage
if __name__ == '__main__':
    creds = authenticate()
    service = build_service(creds)
    print("Listing all files in Google Drive:")
    list_files(service)
    file_name_to_download = input("Enter the name of the file to download: ")
    download_file(service, file_name_to_download)