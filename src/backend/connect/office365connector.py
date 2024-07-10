import os
import json
import requests
import msal
import time
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
import io
import httpx
import asyncio

# Load environment variables from .env file
load_dotenv()

# Azure AD configuration
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
AUTHORITY = os.getenv('AUTHORITY')
REDIRECT_URI = os.getenv('REDIRECT_URI')
SCOPE = ['Files.Read', 'Mail.Read', 'Calendars.Read', 'Contacts.Read', 'Tasks.Read', 'Sites.Read.All']

# Initialize the MSAL confidential client
msal_app = msal.ConfidentialClientApplication(
    CLIENT_ID, authority=AUTHORITY,
    client_credential=CLIENT_SECRET,
)

def get_auth_url():
    return msal_app.get_authorization_request_url(SCOPE, redirect_uri=REDIRECT_URI)

def get_token_by_code(code):
    result = msal_app.acquire_token_by_authorization_code(code, scopes=SCOPE, redirect_uri=REDIRECT_URI)
    return result

def list_files(access_token, folder_id='root'):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(f'https://graph.microsoft.com/v1.0/me/drive/{folder_id}/children', headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.json()}")
    
    files = response.json().get('value', [])
    for file in files:
        if 'folder' in file:
            # print(f"{file['name']} ({file['id']}) - folder")
            list_files(access_token, f"items/{file['id']}")  # Recursive call
        else:
            print(f"{file['name']} ({file['id']}) - {file['file']['mimeType'] if 'file' in file else 'unknown'}")
    return files

def list_emails(access_token, folder='inbox', top=10):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(f'https://graph.microsoft.com/v1.0/me/mailFolders/{folder}/messages?$top={top}', headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.json()}")
    
    emails = response.json().get('value', [])
    for email in emails:
        print(f"Subject: {email['subject']}, Received: {email['receivedDateTime']}, From: {email['from']['emailAddress']['address']}")
        download_email(access_token, email['id'], email['subject'])
    return emails

def download_email(access_token, email_id, email_subject):
    headers = {'Authorization': f'Bearer {access_token}', 'Accept': 'application/vnd.ms-outlook'}
    response = requests.get(f'https://graph.microsoft.com/v1.0/me/messages/{email_id}/$value', headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.json()}")
    
    safe_subject = ''.join(c for c in email_subject if c.isalnum() or c in (' ', '_')).rstrip()
    file_name = f"{safe_subject}.mht"
    
    # Define the directory path
    directory_path = os.path.join(os.getcwd(), 'office365', 'email')
    
    # Create the directory if it does not exist
    os.makedirs(directory_path, exist_ok=True)
    
    # Ensure the file name is unique
    file_path = os.path.join(directory_path, file_name)
    if os.path.exists(file_path):
        # If the file already exists, add a timestamp to the file name
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        file_name = f"{safe_subject}_{timestamp}.mht"
        file_path = os.path.join(directory_path, file_name)
    
    print(file_path)
    
    # Write the email content to the file
    with open(file_path, 'wb') as f:
        f.write(response.content)
    print(f"Email saved as {file_path}")

def list_calendar_events(access_token, top=10):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(f'https://graph.microsoft.com/v1.0/me/events?$top={top}', headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.json()}")
    
    events = response.json().get('value', [])
    
    # Ensure the directory exists
    directory = os.path.join(os.getcwd(), 'office365', 'events')
    os.makedirs(directory, exist_ok=True)
    
    for event in events:
        event_metadata = {
            "subject": event.get('subject', 'N/A'),
            "body": event.get('body', {}).get('content', 'N/A'),
            "bodyPreview": event.get('bodyPreview', 'N/A'),
            "start": event.get('start', {}).get('dateTime', 'N/A'),
            "end": event.get('end', {}).get('dateTime', 'N/A'),
            "location": event.get('location', {}).get('displayName', 'N/A'),
            "attendees": [attendee['emailAddress']['name'] for attendee in event.get('attendees', [])],
            "organizer": event.get('organizer', {}).get('emailAddress', {}).get('name', 'N/A'),
            "isAllDay": event.get('isAllDay', 'N/A'),
            "isCancelled": event.get('isCancelled', 'N/A'),
            "isOrganizer": event.get('isOrganizer', 'N/A'),
            "importance": event.get('importance', 'N/A'),
            "showAs": event.get('showAs', 'N/A'),
            "onlineMeetingUrl": event.get('onlineMeetingUrl', 'N/A'),
            "responseStatus": event.get('responseStatus', {}).get('response', 'N/A'),
            "categories": event.get('categories', []),
            "reminderMinutesBeforeStart": event.get('reminderMinutesBeforeStart', 'N/A'),
            "recurrence": event.get('recurrence', 'N/A'),
            "seriesMasterId": event.get('seriesMasterId', 'N/A'),
            "webLink": event.get('webLink', 'N/A'),
            "sensitivity": event.get('sensitivity', 'N/A'),
            "hasAttachments": event.get('hasAttachments', 'N/A'),
            "attachments": event.get('attachments', []),
            "createdDateTime": event.get('createdDateTime', 'N/A'),
            "lastModifiedDateTime": event.get('lastModifiedDateTime', 'N/A'),
        }

        # Sanitize the event subject to be a valid filename
        filename = f"{event['subject']}.txt".replace('/', '_').replace('\\', '_')
        filepath = os.path.join(directory, filename)
        
        # Save to a .txt file
        with open(filepath, 'w') as file:
            json.dump(event_metadata, file, indent=4)
    
    return events

def list_contacts(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://graph.microsoft.com/v1.0/me/contacts', headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.json()}")
    
    contacts = response.json().get('value', [])
    
    # Ensure the directory exists
    directory = os.path.join(os.getcwd(), 'office365', 'contacts')
    os.makedirs(directory, exist_ok=True)
    
    for contact in contacts:
        contact_metadata = {
            "id": contact.get('id', 'N/A'),
            "displayName": contact.get('displayName', 'N/A'),
            "givenName": contact.get('givenName', 'N/A'),
            "surname": contact.get('surname', 'N/A'),
            "emailAddresses": [email['address'] for email in contact.get('emailAddresses', [])],
            "businessPhones": contact.get('businessPhones', []),
            "homePhones": contact.get('homePhones', []),
            "mobilePhone": contact.get('mobilePhone', 'N/A'),
            "companyName": contact.get('companyName', 'N/A'),
            "jobTitle": contact.get('jobTitle', 'N/A'),
            "department": contact.get('department', 'N/A'),
            "officeLocation": contact.get('officeLocation', 'N/A'),
            "profession": contact.get('profession', 'N/A'),
            "businessAddress": contact.get('businessAddress', 'N/A'),
            "homeAddress": contact.get('homeAddress', 'N/A'),
            "birthday": contact.get('birthday', 'N/A'),
            "personalNotes": contact.get('personalNotes', 'N/A'),
            "assistantName": contact.get('assistantName', 'N/A'),
            "manager": contact.get('manager', 'N/A'),
            "spouseName": contact.get('spouseName', 'N/A'),
            "children": contact.get('children', 'N/A'),
            "createdDateTime": contact.get('createdDateTime', 'N/A'),
            "lastModifiedDateTime": contact.get('lastModifiedDateTime', 'N/A'),
        }

        # Sanitize the contact display name to be a valid filename
        filename = f"{contact['displayName']}.txt".replace('/', '_').replace('\\', '_')
        filepath = os.path.join(directory, filename)
        
        # Save to a .txt file
        with open(filepath, 'w') as file:
            json.dump(contact_metadata, file, indent=4)
    
    return contacts

def list_tasks(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://graph.microsoft.com/v1.0/me/todo/lists', headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.json()}")
    
    task_lists = response.json().get('value', [])
    for task_list in task_lists:
        print(f"Task List: {task_list['displayName']}")
        tasks_response = requests.get(f'https://graph.microsoft.com/v1.0/me/todo/lists/{task_list["id"]}/tasks', headers=headers)
        tasks = tasks_response.json().get('value', [])
        for task in tasks:
            print(f"  Task: {task['title']}")
    return task_lists

def list_sharepoint_sites(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://graph.microsoft.com/v1.0/sites?search=*', headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.json()}")
    
    sites = response.json().get('value', [])
    for site in sites:
        print(f"Site: {site['displayName']} - {site['id']}")
    return sites

def download_file(access_token, file_name):
    files = list_files(access_token)
    file_id = None
    for file in files:
        if file['name'] == file_name:
            file_id = file['id']
            break
    if not file_id:
        print(f"File named {file_name} not found.")
        return
    
    headers = {'Authorization': f'Bearer {access_token}'}
    download_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content'
    response = requests.get(download_url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.json()}")
    
    file_path = os.path.join(os.getcwd(), file_name)
    
    with open(file_path, 'wb') as f:
        f.write(response.content)
    print(f"File downloaded as {file_path}")


async def download_file_by_type(access_token, file_name, user_id):
    async with httpx.AsyncClient() as client:
        if "." not in file_name:
            print(f"File name {file_name} does not contain a '.'")
            return None

        files = list_files(access_token)
        file_id = None
        for file in files:
            if file['name'] == file_name:
                file_id = file['id']
                break

        if not file_id:
            print(f"File named {file_name} not found.")
            return None

        headers = {'Authorization': f'Bearer {access_token}'}
        download_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content'
        response = requests.get(download_url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Error: {response.status_code} - {response.json()}")

        # Sending the file content to the endpoint
        file_content = response.content
        file_stream = io.BytesIO(file_content)
        files = {'file': (file_name, file_stream, 'application/octet-stream')}
        data = {'from_source': 'office365'}
        response = await client.post(f"http://localhost:8000/load_query/{user_id}", files=files, data=data)
        print(f"Response from server: {response.text}")
        if response.status_code == 202:
            print(f"File {file_name} accepted for loading")
        else:
            print(f"File {file_name} was not accepted for loading. Status code: {response.status_code}")

        return response.status_code

async def download_files(access_token, user_id, folder_id='root'):
    try:
        files = list_files(access_token, folder_id)
        
        tasks = []
        for file in files:
            file_name = file['name']
            tasks.append(download_file_by_type(access_token, file_name, user_id))

        # Run all download tasks concurrently
        results = await asyncio.gather(*tasks)

        # Collect names of successfully downloaded files
        downloaded_files = [files[i]['name'] for i in range(len(files)) if results[i] == 202]

    except Exception as e:
        print(f"An error occurred: {e}")
        downloaded_files = []
    
    return downloaded_files

# Example usage
if __name__ == '__main__':
    access_token = authenticate()
    # print("Listing the last 10 received emails in Outlook:")
    # list_emails(access_token, folder='inbox', top=10)
    
    # print("Listing the last 10 sent emails in Outlook:")
    # list_emails(access_token, folder='sentitems', top=10)
    
    # print("Listing the next 10 calendar events:")
    # list_calendar_events(access_token)
    
    print("Listing contacts in Outlook:")   
    list_contacts(access_token)
    
    # print("Listing tasks in Microsoft To-Do:")
    # print(download_files(access_token))
    
    # Commented out because not all ms accounts have the sharepoint app
    #print("Listing SharePoint sites:")
    #list_sharepoint_sites(access_token)
    
    #file_name_to_download = input("Enter the name of the file to download: ")
    #download_file(access_token, file_name_to_download)