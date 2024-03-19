import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")

def desc_gen(input):

    client = OpenAI(
        api_key = OPENAI_KEY
    )

    chat_completion = client.chat.completions.create(
        messages = [
            {
                "role": "user",
              
                "content": f"If the input's structure is pandas dataframe, then infer what the table description. if the format is text only, then please describe it as a pdf file. Here is the input {input}. Return just the description - as detailed as possible, but keep it straight to the point"
            }
        ],
        model = "gpt-4-0125-preview",
    ) 

    return chat_completion.choices[0].message.content
