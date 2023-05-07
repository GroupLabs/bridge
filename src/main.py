from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import openai

from utils import HealthCheckResponse, Query, PARAMS, init, retrieve_context, retrieve_answer, generate_code

app = FastAPI() # init FastAPI
params = PARAMS() # init parameters

index = init() # initialize openai and pinecone connection

# health check
@app.get("/health-check")
async def health():
    return {"health check": HealthCheckResponse.OK, "parameters": {"DEBUG": params.DEBUG,
                                                                   "EMBEDDING MODEL": params.EMBEDDING_MODEL, 
                                                                   "CHAT MODEL": params.CHAT_MODEL}}

# find and return answers to query
@app.get("/")
async def get_answer(query: Query):
    
    gen_ans = retrieve_answer(query=query.query, 
                             index=index, 
                             chat_model=params.CHAT_MODEL, 
                             embedding_model=params.EMBEDDING_MODEL, 
                             prompt_template=params.PROMPT_TEMPLATE,
                             log=params.LOGGING_ENABLED,
                             log_namespace=params.LOGS_NAMESPACE)

    return {"answer": gen_ans,
            "query": query.query,
            "health check": HealthCheckResponse.OK}
 
## EXPERIMENTAL

@app.get("/execute")
async def get_answer(query: Query):

    # Spawn a new process to execute the query
    # Remove any import os, sys, etc. from the query -> activate failure mode

    generated_code = generate_code(query.query, params.MODEL)

    exec(generated_code)

    return {"answer": gen_ans,
            "query": query.query,
            "health check": HealthCheckResponse.OK}
 
# test streaming:
# curl -X GET -H "Content-Type: application/json" -d '{"query": "What is SAGD?", "streaming": true}' http://localhost:8000/experimental-streaming

import time

# generator function to stream openai response
def chat(query: str, context: str):
    response = openai.ChatCompletion.create(
        model=params.CHAT_MODEL,
        messages=[
            {'role': 'user', 'content': params.PROMPT_TEMPLATE.format(context=context, question=query)}
        ],
        temperature=0,
        stream=True  # this time, we set stream=True
    )

    for chunk in response:
        if(chunk["choices"][0]["finish_reason"] == None):
            if("content" in chunk["choices"][0]["delta"]):

                yield str(chunk["choices"][0]["delta"])
        else:
            return
        time.sleep(0.8)

# try streaming response
@app.get("/experimental-streaming")
async def request_handler(query: Query):
    context = retrieve_context(query=query.query, index=index, embedding_model=params.EMBEDDING_MODEL)
    return StreamingResponse(chat(query.query, context))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)