from fastapi import Depends, FastAPI, Response, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import os
import json
import logging
import httpx

from log import setup_logger
from storage import load_data, load_model, query, get_inference
from serverutils import Health, Status, Load
from serverutils import Query
from serverutils import ChatRequest
from ollama import chat, gen
from config import config
from integration_layer import parse_config_from_string
from integration_layer import prepare_inputs_for_model
from integration_layer import format_model_inputs
from elasticutils import Search  # Import the Search class
from serverutils import Connection
from connect.mongodb import get_mongo_connection, get_mongo_connection_with_credentials
from connect.mysql import mysql_to_yamls, mysql_to_yamls_with_connection_string
from connect.postgres import postgres_to_croissant, postgres_to_croissant_with_connection_string
from connect.azure import azure_to_yamls, azure_to_yamls_with_connection_string


TEMP_DIR = config.TEMP_DIR

logger = setup_logger("api")
logger.info("LOGGER READY")

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    print("Exit Process")

app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost:3000",  # Add the origin(s) you want to allow
]

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
    return {"task_id": task_id, "status": task.state}

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
async def load_model_ep(response: Response, model: UploadFile = File(...), config: UploadFile = File(...), description: str = Form(...)):
    try:
        os.makedirs(f"{TEMP_DIR}/models", exist_ok=True)
        model_path = f"{TEMP_DIR}/models/{model.filename}"
        config_path = f"{TEMP_DIR}/models/{config.filename}"
        with open(model_path, "wb") as temp_file:
            temp_file.write(await model.read())
        with open(config_path, "wb") as temp_file:
            temp_file.write(await config.read())
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
        data_dict = json.loads(data)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decoding error: {e}")
        return {"error": "Invalid JSON input"}

    results = get_inference(model, data_dict)
    if results is None:
        return "not a valid model"

    results_serializable = {}
    for key in results.keys():
        if type(results[key]) == list:
            results_serializable[key] = results[key]
        else:
            results_serializable[key] = results[key].tolist()
    return results_serializable

@app.post("/query")
async def nl_query(input: Query):
    resp = query(input.query, input.index)
    logger.info(f"QUERY success: {input.query}")
    return {"health": health, "status": "success", "resp": resp}

# Create an instance of Search class
search = Search()

async def string_to_async_generator(response_string: str):
    yield response_string

@app.post("/chat")
async def chat_with_model(chat_request: ChatRequest):
    try:
        response_message = gen(chat_request.message)  # Assume gen returns a string
        async_generator = string_to_async_generator(response_message)

        search.save_chat_to_history(chat_request.id, chat_request.message, response_message)
        return StreamingResponse(async_generator, media_type="application/json")
    except Exception as e:
        logger.error(f"Error during chat: {str(e)}")
        return {"error": str(e)}

@app.get("/chat_history/{history_id}")
async def get_chat_history(history_id: int):
    try:
        response = search.es.search(index='chat_history', query={'match': {'history_id': history_id}})
        if response['hits']['total']['value'] > 0:
            return response['hits']['hits'][0]['_source']
        else:
            return {"error": "Chat history not found"}
    except Exception as e:
        logger.error(f"Error retrieving chat history: {str(e)}")
        return {"error": str(e)}

@app.post("/ping_database")
async def ping_database(input: Connection):
    client = None

    if input.connectionString:
        if input.database == "mongodb":
            db_func_map_connection_string = {
            "mysql": mysql_to_yamls_with_connection_string,
            "postgres": postgres_to_croissant_with_connection_string,
            "azure": azure_to_yamls_with_connection_string,
            "mongodb": get_mongo_connection
        }
        if input.database in db_func_map_connection_string:
            client = db_func_map_connection_string[input.database](input.connectionString)

    elif input.host and input.user:
        db_func_map_credentials = {
            "mysql": mysql_to_yamls,
            "postgres": postgres_to_croissant,
            "azure": azure_to_yamls,
            "mongodb": get_mongo_connection_with_credentials
        }
        if input.database in db_func_map_credentials:
            client = db_func_map_credentials[input.database](input.host, input.user, input.password)

    print(client)
    return {"client": "ok" if client else "error"}

        
if __name__ == "__main__":
    import uvicorn
    if not config.ENV:
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