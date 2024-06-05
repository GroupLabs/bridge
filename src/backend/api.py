
from fastapi import Depends, FastAPI, Response, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import os
import json

from log import setup_logger
from storage import load_data, load_model, query, get_inference, add_model_to_mlflow, sort_docs, get_parent
from serverutils import Health, Status, Load, Query

from serverutils import ChatRequest
# from ollama import chat, gen
# from ollama import chat, gen
from config import config
from integration_layer import parse_config_from_string
from integration_layer import prepare_inputs_for_model
from integration_layer import format_model_inputs


TEMP_DIR = config.TEMP_DIR

logger = setup_logger("api")
logger.info("LOGGER READY")

# https://fastapi.tiangolo.com/advanced/events/
@asynccontextmanager
async def lifespan(app: FastAPI):

    yield
    # free_db(dbconn)
    # free resources
    # telemetry?

    print("Exit Process")

app = FastAPI(lifespan=lifespan)

# Global variable to keep track of the last sort type and order
last_sort_type = None
last_sort_order = "asc"



origins = [
    "http://localhost:3000",  # Add the origin(s) you want to allow
    # You can add more origins as needed, or use "*" to allow all origins (not recommended for production)
]

# TODO remove CORS

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Specifies which origins are permitted
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.get("/health-check")
async def health_endpoint():
    return {"health": health}


@app.get("/task/{task_id}")
async def get_task_result(task_id: str):
    task = load_data.AsyncResult(task_id)

    # return result obj
    # if task.state == 'SUCCESS':
    #     result = task.get(timeout=1)
    #     return {"task_id": task_id, "status": task.state, "result": result}

    return {"task_id": task_id, "status": task.state}

# load collection (dir)/document (pdf, txt) or database (postgres, mssql, duckdb)/table (csv, tsv, parquet)
# accepts path to data (unstructurded | structured)
# returns ok

@app.post("/load_by_path")
async def load_data_by_path(input: Load, response: Response):
    try:
        task = load_data.delay(input.filepath)
        response.status_code = 202
        logger.info(f"LOAD accepted: {input.filepath}")
        return {"status": "accepted", "task_id": task.id}
    except NotImplementedError:
        logger.warn(f"LOAD incomplete: {input.filepath}")
        response.status_code = 400
        return {"health": "ok", "status": "fail", "reason": "file type not implemented"}

@app.post("/load")
async def load_data_ep(response: Response, file: UploadFile = File(...)):
    try:
        os.makedirs(TEMP_DIR, exist_ok=True)

        with open(f"{TEMP_DIR}/{file.filename}", "wb") as temp_file:
            temp_file.write(await file.read())

        task = load_data.delay(f"{TEMP_DIR}/{file.filename}")
        response.status_code = 202
        logger.info(f"LOAD accepted: {file.filename}")
        return {"status": "accepted", "task_id": task.id}
    except NotImplementedError:
        logger.warn(f"LOAD incomplete: {file.filename}")
        response.status_code = 400
        return {"health": "ok", "status": "fail", "reason": "file type not implemented"}
    
@app.post("/load_model")
#add description
async def load_model_ep(response: Response, model: UploadFile = File(...), config: UploadFile = File(...), description: str=Form(...)):
    try:
        os.makedirs(f"{TEMP_DIR}/models", exist_ok=True)

        model_path = f"{TEMP_DIR}/models/{model.filename}"
        config_path = f"{TEMP_DIR}/models/{config.filename}"

        with open(model_path, "wb") as temp_file:
            temp_file.write(await model.read())

        with open(config_path, "wb") as temp_file:
            temp_file.write(await config.read())

        add_model_to_mlflow(model_path)

        add_model_to_mlflow(model_path)

        task = load_model.delay(model=model_path, config=config_path, description=description)
        response.status_code = 202
        logger.info(f"LOAD accepted: {model.filename}")
        return {"status": "accepted", "task_id": task.id}
    except NotImplementedError:
        logger.warn(f"LOAD incomplete: {model.filename}")
        response.status_code = 400
        return {"health": "ok", "status": "fail", "reason": "file type not implemented"}


@app.post("/get_inference")
async def get_inference_ep(model: str = Form(...), data: str = Form(...)):

    try:
        # Parse the input string to a dictionary
        data_dict = json.loads(data)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decoding error: {e}")
        return {"error": "Invalid JSON input"}

    
    results = get_inference(model,data_dict)
    
    if results is None:
        return "not a valid model"

    results_serializable = {} 

    for key in results.keys():
        if type(results[key]) == list:
            results_serializable[key] = results[key]
        else:
            results_serializable[key] = results[key].tolist()

    return results_serializable


# search
# accepts NL query
# returns distance

@app.post("/query")
async def nl_query(input: Query):
    
    resp = query(input.query, input.index)

    if input.use_llm:
        # context_list = [x["fields"]["text"] for x in resp.hits] this is for vespa, need to switch to es

        prompt = f"{input.query}\n"
        prompt += "Use the following for context:\n"
        # prompt += " ".join(context_list) this is for vespa, need to switch to es

    logger.info(f"QUERY success: {input.query}")

    return {"health": health, "status" : "success", "resp" : resp}

@app.post("/sort")
async def sort_docs_ep(type: str = Form(...)):
    global last_sort_type, last_sort_order
    type_of_sort = ["name", "size", "type", "created"]
    if type not in type_of_sort:
        return "invalid sort"

    # Determine the sort order
    if type == last_sort_type:
        # Toggle the sort order
        if last_sort_order == "asc":
            sort_order = "desc"
        else:
            sort_order = "asc"
    else:
        sort_order = "asc"  # Default to ascending for a new sort type

    # Update the last sort type and order
    last_sort_type = type
    last_sort_order = sort_order


    return sort_docs(type, sort_order)

@app.post("/get_parent")
async def get_parent_ep(chunk: str=Form(...)):
    return get_parent(chunk)

@app.post("/query_parent")
async def get_query_parent_ep(input: Query):
    names = set()
    resp = query(input.query, input.index)

    if input.use_llm:
        # context_list = [x["fields"]["text"] for x in resp.hits] this is for vespa, need to switch to es

        prompt = f"{input.query}\n"
        prompt += "Use the following for context:\n"
        # prompt += " ".join(context_list) this is for vespa, need to switch to es

    for elements in resp:
        if len(names) > 10:
            break
        text_chunk = elements[1]["text"]
        names.add(get_parent(text_chunk))
        
    
    return names

#endpoint to chat with gpt-4:
#to do: stream the response
# @app.post("/chat")
# async def chat_with_model(chat_request: ChatRequest):
#     chat_generator = gen(chat_request.message)
#     return chat_generator

# this one streams
# @app.get("/llm")
# async def llm_query(input: Query):
#     messages = [{"role": "user", "content": input.query}]
    
#     chat_stream = chat(messages) # asynchronous generator

#     return StreamingResponse(chat_stream, media_type="text/plain")
# @app.post("/chat")
# async def chat_with_model(chat_request: ChatRequest):
#     chat_generator = gen(chat_request.message)
#     return chat_generator

# this one streams
# @app.get("/llm")
# async def llm_query(input: Query):
#     messages = [{"role": "user", "content": input.query}]
    
#     chat_stream = chat(messages) # asynchronous generator

#     return StreamingResponse(chat_stream, media_type="text/plain")

# async def json_stream(async_generator):
#     yield '{"messages":['
#     first = True
#    async for item in async_generator:
#         if not first:
#             yield ','
#         first = False
#         yield json.dumps(item)
#     yield ']}'

# from typing import Optional
# from fastapi import Query, FastAPI

# @app.get("/query")
# async def nl_query(query_str: str = Query(..., alias="query"), use_llm: Optional[bool] = False):
#     resp = query(query_str)

#     if use_llm:
#         context_list = [x["fields"]["text"] for x in resp.hits]
#         prompt = f"{query_str}\n"
#         prompt += "Use the following for context:\n"
#         prompt += " ".join(context_list)

#     logger.info(f"QUERY success: {query_str}")
#     return resp
    # return {"status": "success", "resp": [(x["fields"]["text"], x["fields"]["matchfeatures"]) for x in resp.hits]}





if __name__ == "__main__":
    import uvicorn

    if not config.ENV: # requires environment declaration
        print("Missing environment variable.")
        exit(1)

    if config.ENV == "DEBUG":
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try: 
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]

            print("\n\nServer available @ http://" + ip_address + ":" + str(config.PORT) + "\n\n")
        except OSError as e:
            print(e)

    if config.ENV == "PROD":
        print("Please consider the following command to start the server:")
        print("\t EXPERIMENTAL: uvicorn your_app_module:app --workers 3")
        
    global health 
    health = Health(status=Status.OK, ENV=config.ENV)
    logger.info("SYSTEM READY")
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
