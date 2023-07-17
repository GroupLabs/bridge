from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from serverutils import HealthCheckResponse, Query
from utils import PARAMS, init_apis, vec_db, llm, log_question_answer

app = FastAPI() # init FastAPI
params = PARAMS() # init parameters
index = init_apis() # initialize openai and pinecone connection

# health check
@app.get("/health-check")
async def health():
    return {"health check": HealthCheckResponse.OK, "parameters": {"DEBUG": params.DEBUG,
                                                                   "EMBEDDING MODEL": params.EMBEDDING_MODEL, 
                                                                   "CHAT MODEL": params.CHAT_MODEL}}

# find and return answers to query
@app.get("/contextual-answer")
async def contextual_answer(query: Query):

    # find context
    context = vec_db(query=query.query, index=index, embedding_model=params.EMBEDDING_MODEL)

    # build prompt
    prompt = params.prompts["contextual-answer"].format(context=context, query=query.query)

    # llm to generate answer
    contextual_answer = llm(prompt=prompt, MODEL=params.CHAT_MODEL)["content"]
    
    if params.LOGGING_ENABLED:
        if params.LOGS_NAMESPACE == '':
            raise NameError("Log namespace is not defined.")
        log_question_answer(index, q_embedding=xq, question=query.query, answer=contextual_answer, _namespace=params.LOGS_NAMESPACE)
    

    return {"answer": contextual_answer,
            "query": query.query,
            "health check": HealthCheckResponse.OK}
 
@app.get("/execute")
async def get_answer(query: Query):

    # Spawn a new process to execute the query
    # Remove any import os, sys, etc. from the query -> activate failure mode | This can hang. We need error handling

    # build prompt
    prompt = params.prompts["code"].format(query=query.query)

    # generate code
    generated_code = llm(prompt=prompt, MODEL=chat_model)["content"]
    
    # clean up generated code
    split_text = generated_code.split("```") # split the generated code by ```
    split_text = split_text[1] if len(split_text) > 1 else "" # extract code string from surrounding ```
    code = split_text.lstrip("`").rstrip("`").lstrip("python") # remove ``` from beginning and end of generated code

    print(code)

    # execute code
    exec(code, globals(), locals())

    if "result" in locals():
        result = locals()['result']
    else:
        result = "No result variable returned."

    return {"answer": result,
            "query": query.query,
            "health check": HealthCheckResponse.OK}
 

########################################################################################################
################################### EXPERIMENTAL #######################################################
########################################################################################################

# test streaming:
# curl -X GET -H "Content-Type: application/json" -d '{"query": "What is SAGD?", "streaming": true}' http://localhost:8000/experimental-streaming

import time
import openai

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
    uvicorn.run(app, host="0.0.0.0", port=8000)