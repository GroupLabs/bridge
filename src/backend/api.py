import os
import json
import logging
import httpx
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from fastapi import Depends, FastAPI, Response, File, UploadFile, Form, Path, Request, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse, JSONResponse, FileResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import subprocess
import time
from log import setup_logger
from storage import load_data, load_model, query, get_inference, sort_docs, get_parent, download_and_load_task, download_office365
from serverutils import Health, Status, Load, Query, QueryforAll
from serverutils import ChatRequest
from ollama import chat1, chat2, gen2, gen1, gen_for_query

from config import config
from integration_layer import parse_config_from_string
from integration_layer import prepare_inputs_for_model
from integration_layer import format_model_inputs
from elasticutils import Search  # Import the Search class
from starlette.middleware.sessions import SessionMiddleware
from elasticutils import Search  # Import the Search class
from serverutils import Connection
from connect.mongodb import get_mongo_connection, get_mongo_connection_with_credentials
from connect.mysql import mysql_to_yamls, mysql_to_yamls_with_connection_string
from connect.postgres import postgres_to_croissant, postgres_to_croissant_with_connection_string
from connect.azure import azure_to_yamls, azure_to_yamls_with_connection_string
from uuid import uuid4
from elasticsearch.exceptions import NotFoundError
import aiofiles
import asyncio
from celery.result import AsyncResult

from pdf2image import convert_from_path
from PIL import Image, ImageDraw, ImageFont
import os

# elasticsearch
es = Search()

# Load environment variables
load_dotenv()

from connect.mongodb import get_mongo_connection, get_mongo_connection_with_credentials
from connect.mysql import mysql_to_yamls, mysql_to_yamls_with_connection_string
from connect.postgres import postgres_to_croissant, postgres_to_croissant_with_connection_string
from connect.azure import azure_to_yamls, azure_to_yamls_with_connection_string
from uuid import uuid4

from elasticsearch.exceptions import NotFoundError
from connect.googleconnector import download_and_load, get_flow
from config import config
import msal
import connect.salesforceconnector as salesforceconnector
import connect.slackconnector as slackconnector
import base64

# elasticsearch
es = Search()

# Load environment variables
load_dotenv()


TEMP_DIR = config.TEMP_DIR
DOWNLOAD_DIR = "downloads"


SCOPE = ['Files.Read', 'Mail.Read', 'Calendars.Read', 'Contacts.Read', 'Tasks.Read', 'Sites.Read.All']

CLIENT_SECRET_FILE = os.getenv('CLIENT_SECRET_FILE')

logger = setup_logger("api")
logger.info("LOGGER READY")


# Initialize the MSAL confidential client
msal_app = msal.ConfidentialClientApplication(
    config.CLIENT_ID, authority=config.AUTHORITY,
    client_credential=config.CLIENT_SECRET,
)
clients = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    print("Exit Process")

app = FastAPI(lifespan=lifespan)

last_sort_type = None
last_sort_order = "asc"

origins = [
    "http://localhost:3000",  # Add the origin(s) you want to allow
    "https://nids22.github.io"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Specifies which origins are permitted
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Add SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key="supersecretkey")

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
    
@app.get("/office_auth")
async def auth():
    try:
        # Step 1: Get authorization URL
        auth_url = msal_app.get_authorization_request_url(SCOPE, redirect_uri=config.REDIRECT_URI)
        
        # Print or return the authorization URL so user can authorize manually
        return JSONResponse(content={"auth_url": auth_url})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/token")
async def get_token(request: Request):
    code = request.query_params.get('code')
    if not code:
        return {"error": "Authorization code not found in the request."}
    
    result = msal_app.acquire_token_by_authorization_code(code, scopes=SCOPE, redirect_uri=config.REDIRECT_URI)
    if 'access_token' not in result:
        return {"error": f"Could not acquire token: {result.get('error_description')}"}
    
    access_token = result['access_token']
    task = download_office365.delay(access_token)

    return {"status": "accepted", "task_id": task.id}

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
=======
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

@app.post("/load_query")
async def load_query_ep(response: Response, file: UploadFile = File(...)):
    try:
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        temp_file_path = f"{TEMP_DIR}/{file.filename}"
        download_file_path = f"{DOWNLOAD_DIR}/{file.filename}"
        filename = file.filename
        total_size = file.size  # Get total size of the file
        current_size = 0
        
        async with aiofiles.open(download_file_path, "wb") as download_file:
            while contents := await file.read(1024):
                await download_file.write(contents)
                current_size += len(contents)
                await update_progress(filename, current_size, total_size)
        
        # Ensure the file pointer is reset to the beginning before reading the content again
        await file.seek(0)
        content = await file.read()
        with open(f"{TEMP_DIR}/{file.filename}", "wb") as temp_file:
            temp_file.write(content)

        # Start the task
        task = load_data.delay(f"{TEMP_DIR}/{file.filename}")
        response.status_code = 202
        logger.info(f"LOAD accepted: {file.filename}")

        # Start a background task to update the task progress
        asyncio.create_task(update_task_progress(filename, task.id))

        return {"status": "accepted", "task_id": task.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
async def update_task_progress(filename, task_id):
    while True:
        # Get the task progress using AsyncResult
        task = AsyncResult(task_id)
        if task.ready():
            # If the task is done, send a final update and break the loop
            for ws in clients.get(filename, []):
                await ws.send_text("Task complete!")
            break
        else:
            # If the task is not done, send a progress update
            for ws in clients.get(filename, []):
                await ws.send_text(f"Task progress: {task.result}%")
        await asyncio.sleep(1)  # sleep for 1 second

async def update_progress(filename, current_size, total_size):
    percentage = (current_size / total_size) * 100
    for ws in clients.get(filename, []):
        await ws.send_text(f"Progress: {percentage:.2f}%")
        if current_size == total_size:
            await ws.send_text("Upload complete!")

@app.websocket("/ws/{filename}")
async def websocket_endpoint(websocket: WebSocket, filename: str):
    await websocket.accept()
    if filename not in clients:
        clients[filename] = []
    clients[filename].append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients[filename].remove(websocket)
        if not clients[filename]:
            del clients[filename]

# @app.post("/load_query")
# async def load_data_ep(response: Response, file: UploadFile = File(...)):
#     try:
#         os.makedirs(TEMP_DIR, exist_ok=True)
#         os.makedirs(DOWNLOAD_DIR, exist_ok=True)
#         with open(f"{TEMP_DIR}/{file.filename}", "wb") as temp_file:
#             content = await file.read()
#             temp_file.write(content)
#         with open(f"{DOWNLOAD_DIR}/{file.filename}", "wb") as download_file:
#             download_file.write(content)

#         task = load_data.delay(f"{TEMP_DIR}/{file.filename}")
#         response.status_code = 202
#         logger.info(f"LOAD accepted: {file.filename}")
#         return {"status": "accepted", "task_id": task.id}
#     except NotImplementedError:
#         logger.warn(f"LOAD incomplete: {file.filename}")
#         response.status_code = 400
#         return {"health": "ok", "status": "fail", "reason": "file type not implemented"}


@app.post("/sort")
async def sort_docs_ep(type: str=Form(...)):
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

# Google Drive Authentication and Picker
@app.get("/google_drive_auth")
async def google_drive_auth(request: Request):
    creds = None
    if os.path.exists('token.json'):
        with open('token.json', 'r') as token_file:
            creds = Credentials.from_authorized_user_info(json.load(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(config.CLIENT_SECRET_FILE, SCOPES)

            creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token_file:
                token_file.write(creds.to_json())

    # Store credentials in session
    request.session['credentials'] = creds.to_json()
    return RedirectResponse(url="/picker")

@app.get("/picker", response_class=HTMLResponse)
async def picker(request: Request):
    creds_json = request.session.get('credentials')
    if not creds_json:
        return RedirectResponse(url="/google_drive_auth")
    creds = Credentials.from_authorized_user_info(json.loads(creds_json), SCOPES)

    picker_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Google Picker Example</title>
        <script type="text/javascript">
            function onApiLoad() {
                gapi.load('picker', {'callback': onPickerApiLoad});
            }

            function onPickerApiLoad() {
                var view = new google.picker.View(google.picker.ViewId.DOCS);
                var picker = new google.picker.PickerBuilder()
                    .setOAuthToken('%s')
                    .addView(view)
                    .setCallback(pickerCallback)
                    .build();
                picker.setVisible(true);
            }

            function pickerCallback(data) {
                var url = 'nothing';
                if (data[google.picker.Response.ACTION] == google.picker.Action.PICKED) {
                    var doc = data[google.picker.Response.DOCUMENTS][0];
                    var id = doc[google.picker.Document.ID];
                    var name = doc[google.picker.Document.NAME];
                    alert('You picked: ' + name);
                    fetch('/selected_file', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({name: name}),
                    }).then(response => {
                        if (response.ok) {
                            window.location = '/done';
                        }
                    });
                }
            }
        </script>
        <script type="text/javascript" src="https://apis.google.com/js/api.js?onload=onApiLoad"></script>
    </head>
    <body>
        <h1>Google Picker</h1>
    </body>
    </html>
    ''' % creds.token

    return HTMLResponse(content=picker_html)

@app.post("/selected_file")
async def selected_file_ep(request: Request):
    data = await request.json()
    print("Selected file: ", data['name'])
    return JSONResponse({'status': 'success'})

@app.get("/done")
async def done_ep():
    return HTMLResponse("File selection complete.")

# Create an instance of Search class
search = Search()

async def string_to_async_generator(response_string: str):
    yield response_string

@app.post("/chat/{user_id}")
async def chat_with_model(chat_request: ChatRequest, user_id: str = Path(...)):
    try:
        response_message = gen1(chat_request.message)  # Assume gen returns a string
        async_generator = string_to_async_generator(response_message)

        search.save_chat_to_history(chat_request.id, chat_request.message, response_message, user_id)
        return StreamingResponse(async_generator, media_type="application/json")
    except Exception as e:
        logger.error(f"Error during chat: {str(e)}")
        return {"error": str(e)}

      
 @app.get("/chat_history/{user_id}/{history_id}")
async def get_chat_history(user_id: str, history_id: int):
    try:
        response = search.es.search(
            index='chat_history', 
            query={
                'bool': {
                    'must': [
                        {'match': {'user_id': user_id}},
                        {'match': {'history_id': history_id}}
                    ]
                }
            }
        )
        if response['hits']['total']['value'] > 0:
            chat_histories = [hit['_source'] for hit in response['hits']['hits']]
            return {"user_id": user_id, "history_id": history_id, "chat_histories": chat_histories}
        else:
            return {"error": "Chat history not found"}
    except Exception as e:
        logger.error(f"Error retrieving chat history: {str(e)}")
        return {"error": str(e)}

@app.get("/get_user_chat_histories/{user_id}")
async def get_user_chat_histories(user_id: str):
    try:
        response = search.es.search(index='chat_history', query={'match': {'user_id': user_id}})
        if response['hits']['total']['value'] > 0:
            chat_history_ids = [hit['_source']['history_id'] for hit in response['hits']['hits']]
            return {"user_id": user_id, "chat_history_ids": chat_history_ids}
        else:
            return {"user_id": user_id, "chat_history_ids": [], "message": "No chat histories found"}
    except Exception as e:
        logger.error(f"Error retrieving chat histories for user {user_id}: {str(e)}")
        return {"error": str(e)}

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
        response = search.es.search(index='db_meta', size=1000)
        if response['hits']['total']['value'] > 0:
            databases = []
            for hit in response['hits']['hits']:
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

def sort_by_score(data):
    sorted_data = sorted(data, key=lambda x: x[1]["score"], reverse=True)
    return sorted_data

def concatenate_top_entries(data, top_n=5):
    sorted_data = sorted(data, key=lambda x: x[1]["score"], reverse=True)
    top_entries = sorted_data[:top_n]
    concatenated_string = ""
    for i, entry in enumerate(top_entries, start=1):
        concatenated_string += f'here is context {i}: "{entry[1]["text"]}"\n'
    return concatenated_string

def get_top_ids(data, top_n=5):
    sorted_data = sorted(data, key=lambda x: x[1]["score"], reverse=True)
    top_entries = sorted_data[:top_n]
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