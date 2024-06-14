import os
import httpx
import io
import json
import http.server
import socketserver
import threading
import webbrowser
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv
from pathlib import Path
from simple_salesforce import Salesforce
import sys
import base64
import hashlib
import urllib.parse
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from log import setup_logger

logger = setup_logger("salesforceconnector")
logger.info("LOGGER READY")

SALESFORCE_CLIENT_ID = '3MVG9JJwBBbcN47K7BLbHoSSgaQFAKI9aEawWgpUL2.8m1b2Gc4TbWny4QBHaRP4VSK2ILt5PVPUVOw4vNicF'
SALESFORCE_CLIENT_SECRET = 'B84C52384E4ED13F0215B7565E3D33BBD6E0BDD6B852411B239D6898515D36C5'
SALESFORCE_REDIRECT_URI = 'http://localhost:8000/callback'
AUTHORIZATION_BASE_URL = 'https://login.salesforce.com/services/oauth2/authorize'
TOKEN_URL = 'https://login.salesforce.com/services/oauth2/token'

oauth_state = {}

class OAuthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/callback'):
            query_components = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            self.server.auth_code = query_components.get('code', [None])[0]
            self.server.received_state = query_components.get('state', [None])[0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'Authentication successful. You can close this window.')
        else:
            self.send_response(404)
            self.end_headers()

def generate_code_verifier():
    return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode('utf-8')

def generate_code_challenge(code_verifier):
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).rstrip(b'=').decode('utf-8')
    return code_challenge

def authenticate():
    global oauth_state

    # Generate PKCE code verifier and challenge
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    logger.info(f"Code Verifier: {code_verifier}")
    logger.info(f"Code Challenge: {code_challenge}")

    # Create an OAuth2 session with PKCE
    oauth = OAuth2Session(
        SALESFORCE_CLIENT_ID, 
        redirect_uri=SALESFORCE_REDIRECT_URI, 
        scope=["api", "refresh_token", "offline_access", "id", "profile", "email", "address", "phone", "full"]
    )
    authorization_url, state = oauth.authorization_url(
        AUTHORIZATION_BASE_URL, 
        code_challenge=code_challenge, 
        code_challenge_method='S256'
    )
    
    oauth_state = {
        'state': state,
        'code_verifier': code_verifier
    }

    logger.info(f"Authorization URL: {authorization_url}")
    
    # Open the browser for user authentication
    webbrowser.open(authorization_url)
    httpd = socketserver.TCPServer(('localhost', 8000), OAuthHandler)

    def serve():
        httpd.handle_request()
    thread = threading.Thread(target=serve)
    thread.start()
    thread.join()

    auth_code = httpd.auth_code
    received_state = httpd.received_state
    logger.info(f"Auth Code: {auth_code}")
    logger.info(f"Received State: {received_state}")

    if auth_code and received_state == oauth_state['state']:
        try:
            # URL decode the authorization code
            auth_code = urllib.parse.unquote(auth_code)
            logger.info(f"Decoded Auth Code: {auth_code}")

            # Fetch the token with PKCE
            token = oauth.fetch_token(
                TOKEN_URL,
                client_secret=SALESFORCE_CLIENT_SECRET,
                code=auth_code,
                code_verifier=oauth_state['code_verifier']
            )
            logger.info(f"Token: {token}")
            return token
        except Exception as e:
            logger.error(f"Error fetching token: {str(e)}")
            raise
    else:
        logger.error("No authorization code received or invalid state.")
        raise ValueError("No authorization code received or invalid state.")

def get_salesforce_instance(token):
    try:
        sf = Salesforce(instance_url=token['instance_url'], session_id=token['access_token'])
        logger.info("Salesforce instance created successfully.")
        return sf
    except Exception as e:
        logger.error(f"Error creating Salesforce instance: {str(e)}")
        return None

def get_user_info(token):
    try:
        headers = {
            'Authorization': f'Bearer {token["access_token"]}'
        }
        user_info_url = 'https://login.salesforce.com/services/oauth2/userinfo'
        response = httpx.get(user_info_url, headers=headers)
        response.raise_for_status()
        user_info = response.json()
        user_id = user_info['user_id']
        logger.info(f"User ID: {user_id}")
        return user_id
    except Exception as e:
        logger.error(f"Error retrieving user info: {str(e)}")
        return None

def get_field_names(sf, object_name):
    try:
        desc = sf.__getattr__(object_name).describe()
        field_names = [field['name'] for field in desc['fields']]
        return field_names
    except Exception as e:
        logger.error(f"Error getting field names for {object_name}: {str(e)}")
        return []

def list_records(sf, object_name):
    try:
        logger.info(f"Attempting to list records for {object_name}")
        fields = get_field_names(sf, object_name)
        if not fields:
            raise ValueError(f"No fields found for {object_name}")
        query = f"SELECT {', '.join(fields)} FROM {object_name} LIMIT 1000"
        records = sf.query(query)
        logger.info(f"Number of records retrieved from {object_name}: {len(records['records'])}")
        return records["records"]
    except Exception as e:
        logger.error(f"Error listing records for {object_name}: {str(e)}")
        return []

def retrieve_tasks(sf, account_id):
    try:
        tasks_query = f"SELECT Id, Subject, ActivityDate, WhoId FROM Task WHERE WhatId = '{account_id}'"
        tasks = sf.query(tasks_query)['records']
        logger.info(f"Number of tasks retrieved for account {account_id}: {len(tasks)}")
        return tasks
    except Exception as e:
        logger.error(f"Error retrieving tasks for account {account_id}: {str(e)}")
        return []

def retrieve_notes(sf, account_id):
    try:
        notes_query = f"SELECT Id, Title, Body FROM Note WHERE ParentId = '{account_id}'"
        notes = sf.query(notes_query)['records']
        logger.info(f"Number of notes retrieved for account {account_id}: {len(notes)}")
        return notes
    except Exception as e:
        logger.error(f"Error retrieving notes for account {account_id}: {str(e)}")
        return []

def retrieve_attachments(sf, account_id):
    try:
        attachments_query = f"SELECT Id, Name FROM Attachment WHERE ParentId = '{account_id}'"
        attachments = sf.query(attachments_query)['records']
        logger.info(f"Number of attachments retrieved for account {account_id}: {len(attachments)}")
        return attachments
    except Exception as e:
        logger.error(f"Error retrieving attachments for account {account_id}: {str(e)}")
        return []

def retrieve_files(sf, user_id):
    try:
        # Query to retrieve files owned by the user
        owned_files_query = f"""
            SELECT ContentDocument.Id, ContentDocument.Title, ContentDocument.LatestPublishedVersionId
            FROM ContentDocumentLink 
            WHERE LinkedEntityId = '{user_id}'
        """
        logger.info(f"Running owned files query: {owned_files_query}")
        owned_files = sf.query(owned_files_query)['records']

        # Get ContentDocumentIds for files linked to the user
        linked_files_query = f"""
            SELECT ContentDocumentId
            FROM ContentDocumentLink 
            WHERE LinkedEntityId = '{user_id}'
        """
        logger.info(f"Running linked files query: {linked_files_query}")
        linked_files = sf.query(linked_files_query)['records']
        content_document_ids = [file['ContentDocumentId'] for file in linked_files]

        if not content_document_ids:
            logger.info("No linked files found.")
            return owned_files

        # Query to retrieve files shared with the user based on ContentDocumentIds
        shared_files_query = f"""
            SELECT Id, Title, LatestPublishedVersionId
            FROM ContentDocument
            WHERE Id IN ({",".join(["'" + doc_id + "'" for doc_id in content_document_ids])})
        """
        logger.info(f"Running shared files query: {shared_files_query}")
        shared_files = sf.query(shared_files_query)['records']

        # Combine the results
        all_files = owned_files + shared_files
        logger.info(f"Number of files retrieved: {len(all_files)}")

        for file in all_files:
            file_id = file.get('Id', 'N/A')
            file_title = file.get('Title', 'N/A')
            logger.info(f"File Title: {file_title}, File Id: {file_id}")

        return all_files
    except Exception as e:
        logger.error(f"Error retrieving files: {str(e)}")
        return []

def download_file(sf, file_id, latest_published_version_id):
    try:
        url = f"{sf.base_url}sobjects/ContentVersion/{latest_published_version_id}/VersionData"
        response = httpx.get(url, headers=sf.headers, timeout=None)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Error downloading file {file_id}: {str(e)}")
        return None

async def send_data_to_endpoint(file_title, file_content):
    async with httpx.AsyncClient() as client:
        file_stream = io.BytesIO(file_content)
        files = {'file': (file_title, file_stream, 'application/octet-stream')}
        response = await client.post("http://localhost:8000/load_query", files=files)
        logger.debug(f"Response from server: {response.text}")
        if response.status_code == 202:
            logger.info(f"{file_title} data accepted for loading")
        else:
            logger.warning(f"{file_title} data was not accepted for loading. Status code: {response.status_code}")

async def download_and_load(token):
    try:
        sf = get_salesforce_instance(token)
        if not sf:
            raise ValueError("Salesforce authentication failed")

        user_id = get_user_info(token)
        if not user_id:
            raise ValueError("Failed to retrieve user ID")

        # Retrieve all accounts
        accounts = list_records(sf, "Account")
        if not accounts:
            logger.warning("No accounts found.")
            return
        
        # For each account, retrieve related tasks, notes, attachments, and events
        for account in accounts:
            account_id = account['Id']
            account_name = account['Name']
            logger.info(f"Retrieving data for Account: {account_name}")

            tasks = retrieve_tasks(sf, account_id)
            notes = retrieve_notes(sf, account_id)
            attachments = retrieve_attachments(sf, account_id)

            if tasks:
                await send_data_to_endpoint(f"Tasks_{account_name}.json", json.dumps(tasks).encode('utf-8'))
            if notes:
                await send_data_to_endpoint(f"Notes_{account_name}.json", json.dumps(notes).encode('utf-8'))
            if attachments:
                await send_data_to_endpoint(f"Attachments_{account_name}.json", json.dumps(attachments).encode('utf-8'))
        
        # Retrieve files owned by the user or shared with the user
        files = retrieve_files(sf, user_id)
        if files:
            for file in files:
                file_id = file.get('Id')
                file_title = file.get('Title')
                latest_published_version_id = file.get('LatestPublishedVersionId')
                if file_id and file_title and latest_published_version_id:
                    file_content = download_file(sf, file_id, latest_published_version_id)
                    if file_content:
                        await send_data_to_endpoint(file_title, file_content)

        logger.info("Salesforce data streamed and sent successfully")
    except Exception as e:
        logger.error(f"Error in downloading and loading Salesforce data: {str(e)}")

# Example usage
if __name__ == '__main__':
    try:
        token = authenticate()
        asyncio.run(download_and_load(token))
    except Exception as e:
        logger.error(f"Failed to run the main process: {str(e)}")
