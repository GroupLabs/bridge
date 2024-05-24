import os
import json
import requests
import msal
import webbrowser
import time
from urllib.parse import urlparse, parse_qs

# Azure AD configuration
CLIENT_ID = '7a161cb9-b4a0-4eaa-86db-46be079c427d'
CLIENT_SECRET = 'Z.-8Q~NZb3MbBW8QNa8luHMrjBbw3MrWXogn7b.m'
AUTHORITY = 'https://login.microsoftonline.com/common'
REDIRECT_URI = 'http://localhost:8080/callback'
SCOPE = ['Files.Read', 'Mail.Read', 'Calendars.Read', 'Contacts.Read', 'Tasks.Read', 'Sites.Read.All']

# Initialize the MSAL confidential client
msal_app = msal.ConfidentialClientApplication(
    CLIENT_ID, authority=AUTHORITY,
    client_credential=CLIENT_SECRET,
)

def authenticate():
    # Create the authorization URL
    auth_url = msal_app.get_authorization_request_url(SCOPE, redirect_uri=REDIRECT_URI)
    print(f"Please go to this URL and authorize the application: {auth_url}")
    webbrowser.open(auth_url)
    
    # Start a simple HTTP server to listen for the callback
    from http.server import BaseHTTPRequestHandler, HTTPServer
    class OAuthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            query_components = parse_qs(urlparse(self.path).query)
            self.server.auth_code = query_components.get('code')
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'You can close this window.')
    
    server = HTTPServer(('localhost', 8080), OAuthHandler)
    server.handle_request()
    
    code = server.auth_code[0] if server.auth_code else None
    if not code:
        raise Exception("Failed to get authorization code")
    
    # Exchange the authorization code for an access token
    result = msal_app.acquire_token_by_authorization_code(code, scopes=SCOPE, redirect_uri=REDIRECT_URI)
    if 'access_token' not in result:
        raise Exception(f"Could not acquire token: {result.get('error_description')}")
    
    return result['access_token']

def list_files(access_token, folder_id='root'):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(f'https://graph.microsoft.com/v1.0/me/drive/{folder_id}/children', headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.json()}")
    
    files = response.json().get('value', [])
    for file in files:
        if 'folder' in file:
            print(f"{file['name']} ({file['id']}) - folder")
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
    return emails

def list_calendar_events(access_token, top=10):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(f'https://graph.microsoft.com/v1.0/me/events?$top={top}', headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.json()}")
    
    events = response.json().get('value', [])
    for event in events:
        print(f"Event: {event['subject']} at {event['start']['dateTime']} to {event['end']['dateTime']}")
    return events

def list_contacts(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://graph.microsoft.com/v1.0/me/contacts', headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.json()}")
    
    contacts = response.json().get('value', [])
    for contact in contacts:
        print(f"Contact: {contact['displayName']} - {contact['emailAddresses'][0]['address'] if contact['emailAddresses'] else 'No email'}")
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
    
    with open(file_name, 'wb') as f:
        f.write(response.content)
    print(f"File downloaded as {file_name}")

# Example usage
if __name__ == '__main__':
    access_token = authenticate()
    #print("Listing all files in OneDrive:")
    #list_files(access_token)
    
    print("Listing the last 10 received emails in Outlook:")
    list_emails(access_token, folder='inbox', top=10)
    
    print("Listing the last 10 sent emails in Outlook:")
    list_emails(access_token, folder='sentitems', top=10)
    
    print("Listing the next 10 calendar events:")
    list_calendar_events(access_token)
    
    print("Listing contacts in Outlook:")
    list_contacts(access_token)
    
    print("Listing tasks in Microsoft To-Do:")
    list_tasks(access_token)
    
    print("Listing SharePoint sites:")
    list_sharepoint_sites(access_token)
    
    #file_name_to_download = input("Enter the name of the file to download: ")
    #download_file(access_token, file_name_to_download)