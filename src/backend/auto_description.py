import pandas as pd 
import numpy as np 
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")

def desc_gen(df, use_openai=False):

    if use_openai: # just to manage API costs for now
        client = OpenAI(
            api_key = OPENAI_KEY
        )

        chat_completion = client.chat.completions.create(
            messages = [
                {
                    "role": "user",
                    "content": f"describe the following table {df}"
                }
            ],
            model = "gpt-3.5-turbo",
        ) 

        return chat_completion.choices[0].message.content
    else:
        return "Table description"

    