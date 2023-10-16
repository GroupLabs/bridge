import requests
import json
import openai
from dotenv import load_dotenv
import os

load_dotenv('.env')

# init openai
openai.api_key = os.getenv("OPENAI_API_KEY")

def decode_code(generated_code):
    try:
        split_text = generated_code.split("```")
        split_text = split_text[1] if len(split_text) > 1 else ""
        extracted_code = split_text.lstrip("`").rstrip("`").lstrip("python")
        
        # Encode and decode to utf-8
        sanitized_code = extracted_code.encode('utf-8', 'ignore').decode('utf-8')
        
        return sanitized_code
        
    except Exception as e:
        print("An exception occurred:", e)
        return ""

def decode_files(input):
    
    output = ""

    for file_dict in input:
        file_name = file_dict.get("name", "Unknown name")
        file_extension = file_dict.get("extension", "Unknown extension")
        columns = file_dict.get("contents", {}).get(file_name, {}).get("columns", "Unknown columns")
        
        output += f"Filename: {file_name}.{file_extension}\n"
        output += f"Columns: {columns}\n"
        
    return output

def llm(prompt, context=[], model="mistral", url="http://localhost:11434/api/generate"):
    
    if model == "gpt-4":
        print("Using GPT-4")
        prompt = prompt.replace('\u201c', '"').replace('\u201d', '"')

        completion = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        stream=False
        )

        result = {
            "content" : completion["choices"][0]["message"]["content"],
            "completion" : completion
        }

        return result["content"]

    else:
        data = {
            "model": model,
            "prompt": prompt,
            "context": context
        }

        response = requests.post(url, json=data, stream=True)

        # Initialize an empty string to hold the consolidated responses
        consolidated_response = ''

        # Iterate over the response content line by line
        for line in response.iter_lines(decode_unicode=True):
            # Check if line has content
            if line:
                # Parse the JSON object from the line
                obj = json.loads(line)

                # Extract and concatenate the 'response' field to the consolidated string
                consolidated_response += obj.get("response", '')
        
        return consolidated_response

if __name__ == "__main__":
    print(llm("Hello, write a fun joke.", url = "http://localhost:11434/api/generate"))
    print(llm("Calculate the number of employees in each department. Here are the relevant tables and columns: appearances.csv, players.csv. Return only Python code and nothing else.", url = "http://localhost:11434/api/generate"))
