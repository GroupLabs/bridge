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

env_path = Path('..') / '.env'
load_dotenv(dotenv_path=env_path)

SALESFORCE_CLIENT_ID = '3MVG9JJwBBbcN47K7BLbHoSSgaQFAKI9aEawWgpUL2.8m1b2Gc4TbWny4QBHaRP4VSK2ILt5PVPUVOw4vNicF'
SALESFORCE_CLIENT_SECRET = 'B84C52384E4ED13F0215B7565E3D33BBD6E0BDD6B852411B239D6898515D36C5'
SALESFORCE_REDIRECT_URI = 'http://localhost:8000/callback'
AUTHORIZATION_BASE_URL = 'https://login.salesforce.com/services/oauth2/authorize'
TOKEN_URL = 'https://login.salesforce.com/services/oauth2/token'

state = None  # Global variable to store state

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
    global state
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

    if auth_code and received_state == state:
        try:
            # URL decode the authorization code
            auth_code = urllib.parse.unquote(auth_code)
            logger.info(f"Decoded Auth Code: {auth_code}")

            # Fetch the token with PKCE
            token = oauth.fetch_token(
                TOKEN_URL,
                client_secret=SALESFORCE_CLIENT_SECRET,
                code=auth_code,
                code_verifier=code_verifier
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
    sf = Salesforce(instance_url=token['instance_url'], session_id=token['access_token'])
    return sf

def get_field_names(sf, object_name):
    try:
        desc = sf.__getattr__(object_name).describe()
        field_names = [field['name'] for field in desc['fields']]
        return field_names
    except Exception as e:
        logger.error(f"Error getting field names for {object_name}: {str(e)}")
        return []

def list_objects(sf):
    try:
        sobjects = sf.describe()["sobjects"]
        logger.info("Salesforce Objects:")
        for obj in sobjects:
            logger.info(f"{obj['name']}: {obj['label']}")
        return sobjects
    except Exception as e:
        logger.error(f"Error listing Salesforce objects: {str(e)}")
        return []

def list_records(sf, object_name):
    try:
        fields = get_field_names(sf, object_name)
        if not fields:
            raise ValueError(f"No fields found for {object_name}")
        query = f"SELECT {', '.join(fields)} FROM {object_name} LIMIT 1000"
        records = sf.query(query)
        logger.info(f"Records from {object_name}:")
        for record in records["records"]:
            logger.info(record)
        return records["records"]
    except Exception as e:
        logger.error(f"Error listing records for {object_name}: {str(e)}")
        return []

async def send_data_to_endpoint(data_type, data):
    async with httpx.AsyncClient() as client:
        file_content = json.dumps(data)
        file_name = f"{data_type}.json"
        file_stream = io.BytesIO(file_content.encode('utf-8'))
        files = {'file': (file_name, file_stream, 'application/json')}
        response = await client.post("http://localhost:8000/load_query", files=files)
        logger.debug(f"Response from server: {response.text}")
        if response.status_code == 202:
            logger.info(f"{data_type} data accepted for loading")
        else:
            logger.warning(f"{data_type} data was not accepted for loading. Status code: {response.status_code}")

async def download_and_load(token):
    try:
        sf = get_salesforce_instance(token)
        if not sf:
            raise ValueError("Salesforce authentication failed")

        # List all objects
        objects = list_objects(sf)
        
        # For each object, list records and send to endpoint
        for obj in objects:
            records = list_records(sf, obj['name'])
            if records:
                await send_data_to_endpoint(obj['name'], records)

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
