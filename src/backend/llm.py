import json
import logging
import httpx
from config import config
from openai import OpenAI
import openai
from log import setup_logger
import base64
import os
import asyncio

# Set up the logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

LLM_MODEL = config.LLM_MODEL #currently set to gpt-3.5 turbo, switch to gpt-4 in .env and docker-compose
OPENAI_KEY = config.OPENAI_KEY

client = openai.OpenAI(
    api_key=OPENAI_KEY
)

def gen_for_query_with_file(file_content):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an assistant that helps with extracting data from documents. Generate a concise summary that captures the most important information in natural language."},
                {"role": "user", "content": f"{file_content}"}
            ],
            max_tokens=500,
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI API error: {e}"


def _json(filepath):
    try:
        with open(filepath, 'r') as file:
            file_content = json.load(file)
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        return f"Failed to read file: {e}"

    response = gen_for_query_with_file(file_content)