
from src.utils import PARAMS, init_apis, llm

params = PARAMS() # init parameters
index = init_apis() # initialize openai and pinecone connection

## Use this file to talk to chatgpt. You can choose the model you want:
## chatgpt-3.5 - params.BASIC_CHAT_MODEL
## chatgpt-4 - params.ADV_CHAT_MODEL

## Ensure environment file is in the same directory as this file


print(llm(prompt='''

I want to make a generic function that can be called by the GPT4 function calling API.
This function will load one of the available models, and make some prediction with respect to some arguments given.

''', model=params.ADV_CHAT_MODEL)["content"])








