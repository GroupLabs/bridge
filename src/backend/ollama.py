import requests
import json
import httpx
from config import config
from openai import OpenAI
from log import setup_logger

logger = setup_logger("ollama")
logger.info("LOGGER READY")

#To do: 
#1. Get ES docs as context

LLM_URL = config.LLM_URL
LLM_MODEL = config.LLM_MODEL #currently set to gpt-3.5 turbo, switch to gpt-4 in .env and docker-compose
OPENAI_KEY = config.OPENAI_KEY

async def chat(messages):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_KEY}'
    }
    data = {
        "model": LLM_MODEL,
        "messages": messages  
    }
    timeout = httpx.Timeout(120.0, read=60.0)  # Increase the timeout duration

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", LLM_URL + "chat/completions", json=data, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_text():
                try:
                    message = json.loads(line)
                    if 'choices' in message and message['choices'][0].get('delta'):
                        yield message['choices'][0]['delta']['content']
                except json.JSONDecodeError:
                    continue  # Skip over lines that cannot be loaded as JSON

#generates the text for a response:
def gen(prompt: str):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_KEY}'
    }
    data = {
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": prompt}]  
    }

    with httpx.Client() as client:
        response = client.post(LLM_URL + "/chat/completions", headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']  # Adjusted path for chat API responses
        else:
            raise Exception("Failed to generate text: " + response.text)

if __name__ == "__main__":
    # Example usage
    print(gen("hi?"))  # Testing the gen function using the correct chat API
