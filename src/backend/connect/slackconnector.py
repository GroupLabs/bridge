import os
import httpx
import json
import base64
import hashlib
import urllib.parse
from requests_oauthlib import OAuth2Session
from config import config
import sys

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
        scope=["channels:read", "channels:history", "users:read", "files:read"]
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