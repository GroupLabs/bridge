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
SCOPE = ['Files.Read']

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

def list_files(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://graph.microsoft.com/v1.0/me/drive/root/children', headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.json()}")
    
    files = response.json().get('value', [])
    if not files:
        print('No files found.')
    else:
        print('Files:')
        for file in files:
            print(f"{file['name']} ({file['id']}) - {file['file']['mimeType'] if 'file' in file else 'folder'}")
    return files

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
    print("Listing all files in OneDrive:")
    list_files(access_token)
    file_name_to_download = input("Enter the name of the file to download: ")
    download_file(access_token, file_name_to_download)