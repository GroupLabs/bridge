import requests
import json
import httpx

LLM_URL = "http://localhost:11434/api/"
LLM_MODEL = "mistral"

async def chat(messages):
    data = {
        "model": LLM_MODEL,
        "messages": messages if messages else []
    }

    data_json = json.dumps(data)

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", LLM_URL + "chat", data=data_json, headers={'Content-Type': 'application/json'}) as response:
            response.raise_for_status()
            
            async for line in response.aiter_raw():
                if line:
                    yield line
                    try:
                        message = json.loads(line)
                    except:
                        continue # in case string cannot be loaded as json, skip
                    if message.get("done", False):
                        break

    
def gen(prompt: str):
    data = {
        "model": "llama2",
        "prompt": prompt
    }

    response = requests.post(LLM_URL+"generate", json=data, stream=True)

    # Handle streaming responses
    for line in response.iter_lines():
        if line:  # filter out keep-alive new lines
            decoded_line = line.decode('utf-8')
            print(decoded_line)
            message = json.loads(decoded_line)
            if message.get("done", False):
                break


    if response.status_code == 200:
        return response.text
    else:
        raise Exception
 

if __name__ == "__main__":
    # print(chat([{"role": "user", "content": "when is the best time to water my plants?"}]))
    print()
    print()
    print(gen("why is the sky blue?"))
