import requests
import json
import httpx
from config import config

LLM_URL = config.LLM_URL
LLM_MODEL = config.LLM_MODEL
OPENAI_KEY = config.OPENAI_KEY

async def chat(messages):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_KEY}'
    }
    data = {
        "model": LLM_MODEL,
        "prompt": "\n".join([msg['content'] for msg in messages]),
    }

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", LLM_URL + "completions", json=data, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_text():
                # Since OpenAI API typically sends a complete JSON per message response, we yield the decoded line
                try:
                    message = json.loads(line)
                    if 'choices' in message and message['choices'][0].get('delta'):
                        yield message['choices'][0]['delta']['content']
                except json.JSONDecodeError:
                    continue  # Skip over lines that cannot be loaded as JSON

def gen(prompt: str):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_KEY}'
    }
    data = {
        "model": LLM_MODEL,
        "prompt": prompt
    }

    with httpx.Client() as client:
        response = client.post(LLM_URL + "completions", headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['choices'][0]['text']
        else:
            raise Exception("Failed to generate text: " + response.text)
 

if __name__ == "__main__":
    # print(chat([{"role": "user", "content": "when is the best time to water my plants?"}]))
    # print()
    print(gen("why is the sky blue?"))
    # print()
    # print(chat("why is the sky blue?"))
