import os
import json
from fastapi import Depends, FastAPI, Response, File, UploadFile, Form, Path, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from log import setup_logger
from storage import load_data, load_model, query, get_inference
from serverutils import Health, Status, Load, Query, Connection

from config import config

from connect.mongodb import get_mongo_connection, get_mongo_connection_with_credentials
from connect.mysql import mysql_to_yamls, mysql_to_yamls_with_connection_string
from connect.postgres import postgres_to_croissant, postgres_to_croissant_with_connection_string
from connect.azure import azure_to_yamls, azure_to_yamls_with_connection_string
from uuid import uuid4

TEMP_DIR = config.TEMP_DIR
DOWNLOAD_DIR = "downloads"
SCOPES = ['https://www.googleapis.com/auth/drive.file']
CLIENT_SECRET_FILE = os.getenv('CLIENT_SECRET_FILE')

logger = setup_logger("api")
logger.info("LOGGER READY")

@asynccontextmanager
async def lifespan(app: FastAPI):

    yield
    # free_db(dbconn)
    # free resources
    # telemetry?

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

    return {"health": health, "status" : "success", "query" : input.query, "resp" : resp}

@app.post("/load_query")
async def load_data_ep(response: Response, file: UploadFile = File(...)):
    try:
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        with open(f"{TEMP_DIR}/{file.filename}", "wb") as temp_file:
            content = await file.read()
            temp_file.write(content)
        with open(f"{DOWNLOAD_DIR}/{file.filename}", "wb") as download_file:
            download_file.write(content)

        task = load_data.delay(f"{TEMP_DIR}/{file.filename}")
        response.status_code = 202
        logger.info(f"LOAD accepted: {file.filename}")
        return {"status": "accepted", "task_id": task.id}
    except NotImplementedError:
        logger.warn(f"LOAD incomplete: {file.filename}")
        response.status_code = 400
        return {"health": "ok", "status": "fail", "reason": "file type not implemented"}

@app.post("/ping_database")
async def ping_database(input: Connection):
    client = None
    connection_id = uuid4()

    if input.connectionString:
        db_func_map_connection_string = {
            "mysql": mysql_to_yamls_with_connection_string,
            "postgres": postgres_to_croissant_with_connection_string,
            "azure": azure_to_yamls_with_connection_string,
            "mongodb": get_mongo_connection
        }
        if input.database in db_func_map_connection_string:
            client = db_func_map_connection_string[input.database](input.connectionString, connection_id)

    elif input.host and input.user:
        db_func_map_credentials = {
            "mysql": mysql_to_yamls,
            "postgres": postgres_to_croissant,
            "azure": azure_to_yamls,
            "mongodb": get_mongo_connection_with_credentials
        }
        if input.database in db_func_map_credentials:
            client = db_func_map_credentials[input.database](input.host, input.user, input.password)
            search.add_connection(input.database, input.host, input.user, input.password, connection_id, None)

    print(client)
    return {"client": "ok" if client else "error"}


@app.get("/databases/")
async def get_databases():
    try:
        response = search.es.search(index='db_meta', size=1000)  # Retrieve up to 1000 documents
        if response['hits']['total']['value'] > 0:
            databases = []
            for hit in response['hits']['hits']:
                # Exclude the 'password' field from each document
                database_info = {key: value for key, value in hit['_source'].items()}
                databases.append(database_info)
            return databases
        else:
            raise HTTPException(status_code=404, detail="No databases found")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Index 'db_meta' not found")
    except Exception as e:
        logger.error(f"Error retrieving databases: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/edit_connection/{connection_id}")
async def edit_connection(input: Connection, connection_id: str = Path()):
    client = None

    if input.connectionString:
        db_func_map_connection_string = {
            "mysql": mysql_to_yamls_with_connection_string,
            "postgres": postgres_to_croissant_with_connection_string,
            "azure": azure_to_yamls_with_connection_string,
            "mongodb": get_mongo_connection
        }
        if input.database in db_func_map_connection_string:
            client = db_func_map_connection_string[input.database](input.connectionString, connection_id)

    elif input.host and input.user:
        db_func_map_credentials = {
            "mysql": mysql_to_yamls,
            "postgres": postgres_to_croissant,
            "azure": azure_to_yamls,
            "mongodb": get_mongo_connection_with_credentials
        }
        if input.database in db_func_map_credentials:
            client = db_func_map_credentials[input.database](input.host, input.user, input.password)
            search.add_connection(input.database, input.host, input.user, input.password, connection_id)

    print(client)
    return {"client": "ok" if client else "error"}


@app.delete("/delete_connection/{connection_id}")
async def delete_connection(connection_id: str = Path()):
    try:
        res = search.es.delete_by_query(
            index='db_meta',
            body={'query': {'match': {'connection_id': connection_id}}}
        )
        if res['deleted'] > 0:
            return {"message": f"Connection with ID {connection_id} deleted successfully."}
        else:
            return {"message": f"No connection with ID {connection_id} found."}
    except Exception as e:
        logger.error(f"Error deleting connection: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

    print(client)
    return {"client": "ok" if client else "error"}

def sort_by_score(data):
    # Sort the data by the "score" in descending order
    sorted_data = sorted(data, key=lambda x: x[1]["score"], reverse=True)
    return sorted_data

def concatenate_top_entries(data, top_n=5):
    # Sort the data by the "score" in descending order
    sorted_data = sorted(data, key=lambda x: x[1]["score"], reverse=True)

    # Get the top N entries
    top_entries = sorted_data[:top_n]

    # Create the concatenated string
    concatenated_string = ""
    for i, entry in enumerate(top_entries, start=1):
        concatenated_string += f'here is context {i}: "{entry[1]["text"]}"\n'

    return concatenated_string

def get_top_ids(data, top_n=5):
    # Sort the data by the "score" in descending order
    sorted_data = sorted(data, key=lambda x: x[1]["score"], reverse=True)

    # Get the top N entries
    top_entries = sorted_data[:top_n]

    # Extract the IDs
    top_ids = [entry[0] for entry in top_entries]

    return top_ids

def find_document_by_id(doc_id, indices):
    for index in indices:
        query = {
            "query": {
                "term": {
                    "_id": doc_id
                }
            }
        }
        response = es.search(index=index, body=query)
        if response['hits']['hits']:
            return response['hits']['hits'][0]['_source']['document_id']
    return None

def find_name_by_document_id(document_id, parent_index = "parent_doc"):
    query = {
        "query": {
            "term": {
                "document_id": document_id
            }
        }
    }
    response = es.search(index=parent_index, body=query)
    if response['hits']['hits']:
        return response['hits']['hits'][0]['_source']['document_name']
    return None

def find_document_by_id_rel_docs(document_id, parent_index="parent_doc"):
    query = {
        "query": {
            "term": {
                "document_id": document_id
            }
        }
    }
    response = es.search(index=parent_index, body=query)
    if response['hits']['hits']:
        return response['hits']['hits'][0]['_source']
    return None

@app.post("/rel_docs")
async def relevant_docs_ep(input: Query):
    docs = []
    indices = ["table_meta", "picture_meta","text_chunk"]
    all_responses = []

    # Loop through the indices and collect responses
    for index in indices:
        resp = query(input.query, index)
        if resp is not None:
            all_responses.append(resp)

    # Concatenate the responses
    flattened_responses = [item for sublist in all_responses for item in sublist]

    sorted_responses = sort_by_score(flattened_responses)

    topids = get_top_ids(sorted_responses)

    for doc_id in topids:
        documents = find_document_by_id(doc_id, indices)
        data = find_document_by_id_rel_docs(documents)
        docs.append(data)

    seen = set()
    unique_documents = []
    for doc in docs:
        doc_id = doc['document_id']
        if doc_id not in seen:
            unique_documents.append(doc)
            seen.add(doc_id)

    return unique_documents

@app.post("/query_all")
async def get_query_parent_ep(input: Query):
    names = set()
    indices = ["table_meta", "picture_meta","text_chunk"]
    all_responses = []

    # Loop through the indices and collect responses
    for index in indices:
        resp = query(input.query, index)
        if resp is not None:
            all_responses.append(resp)
        

    # Concatenate the responses
    flattened_responses = [item for sublist in all_responses for item in sublist]

    sorted_responses = sort_by_score(flattened_responses)

    information = concatenate_top_entries(sorted_responses)

    topids = get_top_ids(sorted_responses)
    for doc_id in topids:
        docs = find_document_by_id(doc_id,indices)
        names.add(find_name_by_document_id(docs))

    chat_generator = gen_for_query(input.query, information, names)
    return StreamingResponse(chat_generator, media_type="text/plain")

# @app.post("/chat")
# async def chat_with_model_ep(chat_request: ChatRequest):
#     chat_generator = gen2(chat_request.message)
#     return StreamingResponse(chat_generator, media_type="text/plain")

@app.post("/load/{user_id}")
async def load_data_ep(response: Response, file: UploadFile = File(...), user_id: str = Path()):
    try:
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        with open(f"{TEMP_DIR}/{file.filename}", "wb") as temp_file:
            content = await file.read()
            temp_file.write(content)
        with open(f"{DOWNLOAD_DIR}/{file.filename}", "wb") as download_file:
            download_file.write(content)
        task = load_data.delay(f"{TEMP_DIR}/{file.filename}", user_id)
        response.status_code = 202
        logger.info(f"LOAD accepted: {file.filename}")
        return {"status": "accepted", "task_id": task.id}
    except NotImplementedError:
        logger.warn(f"LOAD incomplete: {file.filename}")
        response.status_code = 400
        return {"health": "ok", "status": "fail", "reason": "file type not implemented"}
    
@app.get("/downloads/{filename}")
async def download_file(filename: str):
    return FileResponse(f"{DOWNLOAD_DIR}/{filename}")

if __name__ == '__main__':
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
