import requests
import json

LLM_URL = "http://localhost:11434/api/"
LLM_MODEL = "mistral"

def chat(messages): ## NOT suitable for production!
    data = {
        "model": LLM_MODEL,
        "messages": [
            # {"role": "user", "content": "why is the sky blue?"}
        ]
    }

    data_json = json.dumps(data)

    if messages:
        data["messages"] = messages

    response = requests.post(LLM_URL+"chat", data=data_json, headers={'Content-Type': 'application/json'}, stream=True)

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
