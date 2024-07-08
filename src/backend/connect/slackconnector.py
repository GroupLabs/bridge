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
        scope="files:read channels:history groups:history im:history mpim:history im:read mpim:read groups:read channels:read users.profile:read"
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
        logger.debug(f"Files list response: {response.text}")
        response.raise_for_status()
        files = response.json().get('files', [])
        logger.info(f"Number of files retrieved: {len(files)}")
        return files

async def download_file(token, file):
    try:
        file_id = file['id']
        url = f'https://slack.com/api/files.info?file={file_id}'
        headers = {
            'Authorization': f'Bearer {token["access_token"]}'
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            logger.debug(f"File info response for file {file_id}: {response.text}")
            response.raise_for_status()
            file_info = response.json().get('file')
            if file_info:
                file_url = file_info.get('url_private_download')
                if not file_url:
                    logger.error(f"No url_private_download found for file {file_id}")
                    return None, None
                file_content = await client.get(file_url, headers=headers)
                file_content.raise_for_status()
                return file_content.content, file_info['name']
            else:
                logger.error(f"No file info found for file {file_id}")
                return None, None
    except Exception as e:
        logger.error(f"Error downloading file {file['id']}: {str(e)}")
        return None, None

async def send_file_to_endpoint(file_content, file_name, content_type='application/json'):
    logger.info(f"Sending file {file_name} to endpoint")
    async with httpx.AsyncClient() as client:
        file_stream = io.BytesIO(file_content)
        files = {'file': (file_name, file_stream, content_type)}
        response = await client.post("http://localhost:8000/load_query", files=files, from_source="slack")
        logger.debug(f"Response from server: {response.text}")
        if response.status_code == 202:
            logger.info(f"{file_name} data accepted for loading")
        else:
            logger.warning(f"{file_name} data was not accepted for loading. Status code: {response.status_code}")

async def get_user_info(token, user_id):
    url = f'https://slack.com/api/users.info?user={user_id}'
    headers = {
        'Authorization': f'Bearer {token["access_token"]}'
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        logger.debug(f"User info response for user {user_id}: {response.text}")
        response.raise_for_status()
        user_info = response.json()
        user_name = user_info.get('user', {}).get('real_name', 'Unknown User')
        return user_name

async def get_chat_history(token, channel):
    url = f'https://slack.com/api/conversations.history?channel={channel}'
    headers = {
        'Authorization': f'Bearer {token["access_token"]}'
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        logger.debug(f"Chat history response for channel {channel}: {response.text}")
        response.raise_for_status()
        messages = response.json().get('messages', [])
        logger.info(f"Number of messages retrieved from channel {channel}: {len(messages)}")
        return messages

async def save_chat_history_as_text(messages, channel_name, token):
    file_content = io.StringIO()
    for message in messages:
        text = message.get('text', '')
        user_id = message.get('user', 'Unknown User')
        ts = message.get('ts', 'Unknown Timestamp')
        user_name = await get_user_info(token, user_id) if user_id != 'Unknown User' else 'Unknown User'
        file_content.write(f"Timestamp: {ts}\nUser: {user_name}\nMessage: {text}\n\n")
    file_content.seek(0)
    return file_content.read().encode('utf-8'), f"{channel_name}_chat_history.txt"

async def process_files(token):
    try:
        files = await get_files(token)
        for file in files:
            file_content, file_name = await download_file(token, file)
            if file_content and file_name:
                await send_file_to_endpoint(file_content, file_name)
            else:
                logger.warning(f"Failed to download file {file['name']} ({file['id']})")
    except Exception as e:
        logger.error(f"Error in process_files: {str(e)}")

async def process_chat_history(token):
    try:
        url = 'https://slack.com/api/conversations.list'
        headers = {
            'Authorization': f'Bearer {token["access_token"]}'
        }
        params = {
            'types': 'public_channel,private_channel,mpim,im'
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            logger.debug(f"Conversations list response: {response.text}")
            response.raise_for_status()
            channels = response.json()
            channels = channels.get('channels', [])
            logger.info(f"Number of channels retrieved: {len(channels)}")
            
            if not channels:
                logger.warning("No channels retrieved. Check your Slack token permissions and API endpoint.")
            
            for channel in channels:
                logger.info(f"Processing channel: {channel['name']} ({channel['id']})")
                messages = await get_chat_history(token, channel['id'])
                if messages:
                    file_content, file_name = await save_chat_history_as_text(messages, channel['name'], token)
                    await send_file_to_endpoint(file_content, file_name, content_type='text/plain')
                else:
                    logger.warning(f"No messages found for channel: {channel['name']} ({channel['id']})")
    except httpx.HTTPStatusError as http_err:
        logger.error(f"HTTP error occurred: {http_err.response.status_code} - {http_err.response.text}")
    except Exception as err:
        logger.error(f"An error occurred: {str(err)}")

async def process_files_and_chats(token):
    try:
        await process_files(token)
        await process_chat_history(token)
    except Exception as e:
        logger.error(f"Error in process_files_and_chats: {str(e)}")
