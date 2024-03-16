import pandas as pd 
import numpy as np 
import os
try:
    import openai 
except:
    os.system('python -m pip install openai')
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
import requests
import json
load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")

def desc_gen(df):

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