import os
import httpx
import json
import base64
import hashlib
import urllib.parse
from requests_oauthlib import OAuth2Session
import sys
import io

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from log import setup_logger

logger = setup_logger("slackconnector")
logger.info("LOGGER READY")

SLACK_CLIENT_ID = '7279238052193.7274645051095'
SLACK_CLIENT_SECRET = '82cb6085057b1e8b77d7a0afdeb52e70'
SLACK_REDIRECT_URI = 'https://nids22.github.io/Bridge-OAuth/index.html'
SLACK_AUTHORIZATION_BASE_URL = 'https://slack.com/oauth/authorize'
SLACK_TOKEN_URL = 'https://slack.com/api/oauth.access'

def generate_code_verifier():
    return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode('utf-8')

def generate_code_challenge(code_verifier):
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).rstrip(b'=').decode('utf-8')
    return code_challenge

def get_slack_authorization_url():
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    oauth = OAuth2Session(
        SLACK_CLIENT_ID,
        redirect_uri=SLACK_REDIRECT_URI,
        scope=["files:read"]
    )
    authorization_url, state = oauth.authorization_url(
        SLACK_AUTHORIZATION_BASE_URL,
        code_challenge=code_challenge,
        code_challenge_method='S256'
    )

    return authorization_url, state, code_verifier

def fetch_slack_token(code, state, code_verifier):
    oauth = OAuth2Session(
        SLACK_CLIENT_ID,
        redirect_uri=SLACK_REDIRECT_URI,
        state=state
    )
    token = oauth.fetch_token(
        SLACK_TOKEN_URL,
        client_secret=SLACK_CLIENT_SECRET,
        code=code,
        code_verifier=code_verifier
    )
    logger.info(f"Fetched Token: {token}")
    return token

async def get_files(token):
    url = 'https://slack.com/api/files.list'
    headers = {
        'Authorization': f'Bearer {token["access_token"]}'
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        files = response.json().get('files', [])
        logger.info(f"Number of files retrieved: {len(files)}")
        for file in files:
            logger.info(f"File info: {file}")
        return files

async def download_file(token, file):
    file_id = file['id']
    url = f'https://slack.com/api/files.info?file={file_id}'
    headers = {
        'Authorization': f'Bearer {token["access_token"]}'
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        file_info = response.json().get('file')
        if file_info:
            file_url = file_info['url_private_download']
            file_content = await client.get(file_url, headers=headers)
            file_content.raise_for_status()
            return file_content.content, file_info['name']
        return None, None

async def send_file_to_endpoint(file_content, file_name):
    logger.info(f"Sending file {file_name} to endpoint")
    async with httpx.AsyncClient() as client:
        file_stream = io.BytesIO(file_content)
        files = {'file': (file_name, file_stream, 'application/octet-stream')}
        response = await client.post("http://localhost:8000/load_query", files=files)
        logger.debug(f"Response from server: {response.text}")
        if response.status_code == 202:
            logger.info(f"{file_name} data accepted for loading")
        else:
            logger.warning(f"{file_name} data was not accepted for loading. Status code: {response.status_code}")

async def process_files(token):
    files = await get_files(token)
    for file in files:
        file_content, file_name = await download_file(token, file)
        if file_content and file_name:
            await send_file_to_endpoint(file_content, file_name)
        else:
            logger.warning(f"Failed to download file {file['name']} ({file['id']})")
