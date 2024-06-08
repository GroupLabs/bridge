import requests
import json
import httpx
from config import config
from openai import OpenAI
from log import setup_logger
import base64
import os
logger = setup_logger("ollama")
logger.info("LOGGER READY")

#To do: 
#1. Get ES docs as context


LLM_URL = config.LLM_URL
LLM_MODEL = config.LLM_MODEL #currently set to gpt-3.5 turbo, switch to gpt-4 in .env and docker-compose
OPENAI_KEY = config.OPENAI_KEY

client = OpenAI(
    api_key=OPENAI_KEY
)

async def chat1(messages):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_KEY}'
    }
    data = {
        "model": LLM_MODEL,
        "messages": messages  
    }
    timeout = httpx.Timeout(120.0, read=60.0)  # Increase the timeout duration

    async with httpx.AsyncClient(timeout=timeout) as client:
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
def gen1(prompt: str):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_KEY}'
    }
    data = {
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": prompt}]  
    }
    timeout = httpx.Timeout(120.0, read=60.0)  # Increase the timeout duration
    with httpx.Client(timeout=timeout) as client:
        response = client.post(LLM_URL + "/chat/completions", headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']  # Adjusted path for chat API responses
        else:
            raise Exception("Failed to generate text: " + response.text)

async def chat2(messages):
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
async def gen2(prompt: str):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_KEY}'
    }
    data = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "temperature": 0,  
    }

    timeout = httpx.Timeout(300.0, read=300.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", LLM_URL + "/chat/completions", headers=headers, json=data) as response:
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or line == '[DONE]':
                        continue
                    try:
                        event = json.loads(line[len("data: "):])
                        if 'delta' in event['choices'][0] and 'content' in event['choices'][0]['delta']:
                            yield event['choices'][0]['delta']['content']
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        msg = f"get_aichat_reply_openai: Streaming error with OpenAI: {str(e)}"
        logger.info(msg)

#generates the text for a response:
async def gen_for_query(prompt: str, information:str, source: set):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_KEY}'
    }
    data = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": f"answer the following prompt:{prompt}. Base your answer on the following information {information}"}],
        "stream": True,
        "temperature": 0,
    }
    timeout = httpx.Timeout(300.0, read=300.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", LLM_URL + "/chat/completions", headers=headers, json=data) as response:
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or line == '[DONE]':
                        continue
                    try:
                        event = json.loads(line[len("data: "):])
                        if 'delta' in event['choices'][0] and 'content' in event['choices'][0]['delta']:
                            yield event['choices'][0]['delta']['content']
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        msg = f"get_aichat_reply_openai: Streaming error with OpenAI: {str(e)}"
        logger.info(msg)

    # Yield the additional message at the end
    yield f"\n\nThis response is based on these documents. {source}"
        

# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')
    
def chat_with_model_to_get_description(image_path):
    base64_image = encode_image(image_path)
    name = os.path.basename(image_path)


    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_KEY}'
    }
    data = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"The following is a picture, Describe what is in the picture - as detailed as possible, but keep it straight to the point, summarize in 30 words, include the file name. Keep in mind the file name as it might help in your description {name}: "
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    }

    timeout = httpx.Timeout(300.0, read=300.0)

    with httpx.Client(timeout=timeout) as client:
        response = client.post(LLM_URL + "/chat/completions", headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']  # Adjusted path for chat API responses
        else:
            raise Exception("Failed to generate text: " + response.text)

if __name__ == "__main__":
    # Example usage
    print(chat_with_model_to_get_description("/Users/codycf/Desktop/betting/prizepicks_site.jpeg"))  # Testing the gen function using the correct chat API
