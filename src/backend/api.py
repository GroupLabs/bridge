import os
import json
import logging
import httpx
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from fastapi import Depends, FastAPI, Response, File, UploadFile, Form, Path, Request, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
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
from connect.googleconnector import download_and_load, get_flow
from config import config
import msal
import connect.salesforceconnector as salesforceconnector
import connect.slackconnector as slackconnector
import base64
import aiofiles
import asyncio
from celery.result import AsyncResult
from pdf2image import convert_from_path
from PIL import Image, ImageDraw, ImageFont
import os

# elasticsearch
es = Search()


# To store clients and their progress
clients = {}

# Load environment variables
load_dotenv()

TEMP_DIR = config.TEMP_DIR
DOWNLOAD_DIR = "downloads"
SCOPES = ['https://www.googleapis.com/auth/drive.file']
CLIENT_SECRET_FILE = os.getenv('CLIENT_SECRET_FILE')

# Azure AD configuration
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
AUTHORITY = os.getenv('AUTHORITY')
REDIRECT_URI = os.getenv('REDIRECT_URI')
SCOPE = ['Files.Read', 'Mail.Read', 'Calendars.Read', 'Contacts.Read', 'Tasks.Read', 'Sites.Read.All']

logger = setup_logger("api")
logger.info("LOGGER READY")

# Initialize the MSAL confidential client
msal_app = msal.ConfidentialClientApplication(
    CLIENT_ID, authority=AUTHORITY,
    client_credential=CLIENT_SECRET,
)

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
        auth_url = msal_app.get_authorization_request_url(SCOPE, redirect_uri=REDIRECT_URI)
        
        # Print or return the authorization URL so user can authorize manually
        return JSONResponse(content={"auth_url": auth_url})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/token")
async def get_token(request: Request):
    code = request.query_params.get('code')
    if not code:
        return {"error": "Authorization code not found in the request."}
    
    result = msal_app.acquire_token_by_authorization_code(code, scopes=SCOPE, redirect_uri=REDIRECT_URI)
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

    return {"health": health, "status": "success", "resp": resp}
"""
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
"""

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
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
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
        # Query Elasticsearch for all chat histories for the given user_id
        response = search.es.search(index='chat_history', query={'match': {'user_id': user_id}})
        
        # Extract the chat history IDs from the response
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
async def relevant_docs_ep(input: QueryforAll):
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
async def get_query_parent_ep(input: QueryforAll):
    names = set()
    indices = ["table_meta", "picture_meta","text_chunk", "universal_data_index"]
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

@app.post("/chat")
async def chat_with_model_ep(chat_request: ChatRequest):
    chat_generator = gen2(chat_request.message)
    return StreamingResponse(chat_generator, media_type="text/plain")

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

@app.get("/google_auth")
async def google_auth():
    try:
        flow = get_flow()
        auth_url, state = flow.authorization_url(
            access_type='offline',  # Ensure offline access to get a refresh token
            prompt='consent',  # Force consent screen to ensure refresh token is issued
            include_granted_scopes='true'
        )
        logger.debug(f"Generated auth URL: {auth_url} with state: {state}")
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Error during authentication initiation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication initiation failed: {e}")

@app.get("/oauth2callback")
async def oauth_callback(request: Request):
    try:
        state = request.query_params.get('state')
        code = request.query_params.get('code')
        if not state or not code:
            raise HTTPException(status_code=400, detail="Missing state or code parameter")

        logger.debug(f"Received state: {state} and code: {code}")

        flow = get_flow()
        authorization_response = str(request.url)
        logger.debug(f"Received authorization response: {authorization_response}")

        flow.fetch_token(authorization_response=authorization_response)
        creds = flow.credentials
        logger.debug(f"Fetched token with scopes: {creds.scopes}")

        if creds.refresh_token:
            logger.debug("Refresh token received")
        else:
            logger.error("Refresh token is missing")
            raise ValueError("Refresh token is missing")

        # Call the Celery task
        download_and_load_task.delay(creds.to_json())
        
        return {"status": "success", "message": "Authentication successful, download started in background"}
    except Exception as e:
        logger.error(f"Error during OAuth2 callback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication callback failed: {e}")
    
oauth_state = None

@app.get("/salesforce_auth")
def get_salesforce_auth():
    global oauth_state
    # Generate PKCE code verifier and challenge
    code_verifier = salesforceconnector.generate_code_verifier()
    code_challenge = salesforceconnector.generate_code_challenge(code_verifier)

    logger.info(f"Code Verifier: {code_verifier}")
    logger.info(f"Code Challenge: {code_challenge}")

    # Create an OAuth2 session with PKCE
    oauth = salesforceconnector.OAuth2Session(
        salesforceconnector.SALESFORCE_CLIENT_ID, 
        redirect_uri=salesforceconnector.SALESFORCE_REDIRECT_URI, 
        scope=["api", "refresh_token", "offline_access", "id", "profile", "email", "address", "phone", "full"]
    )
    authorization_url, state = oauth.authorization_url(
        salesforceconnector.AUTHORIZATION_BASE_URL, 
        code_challenge=code_challenge, 
        code_challenge_method='S256'
    )

    oauth_state = {
        'state': state,
        'code_verifier': code_verifier
    }

    logger.info(f"Authorization URL: {authorization_url}")

    return JSONResponse(content={"authorization_url": authorization_url})

@app.get("/callback")
async def callback(request: Request):
    global oauth_state
    code = request.query_params.get('code')
    state = request.query_params.get('state')

    if not code or state != oauth_state['state']:
        raise HTTPException(status_code=400, detail="Invalid state or missing code")

    try:
        # Create an OAuth2 session with PKCE
        oauth = salesforceconnector.OAuth2Session(
            salesforceconnector.SALESFORCE_CLIENT_ID, 
            redirect_uri=salesforceconnector.SALESFORCE_REDIRECT_URI, 
            state=oauth_state['state']
        )

        # Exchange the authorization code for a token
        token = oauth.fetch_token(
            salesforceconnector.TOKEN_URL,
            client_secret=salesforceconnector.SALESFORCE_CLIENT_SECRET,
            code=code,
            code_verifier=oauth_state['code_verifier']
        )

        logger.info(f"Token: {token}")

        # Trigger the download and load process
        await salesforceconnector.download_and_load(token)
        
        return JSONResponse(content={"status": "success", "message": "Salesforce data download and load triggered"})
    except Exception as e:
        logger.error(f"Error in callback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
def encode_state(state, code_verifier, session_id):
    state_data = {
        "state": state,
        "code_verifier": code_verifier,
        "session_id": session_id
    }
    state_json = json.dumps(state_data)
    state_encoded = base64.urlsafe_b64encode(state_json.encode()).decode()
    return state_encoded

def decode_state(state_encoded):
    state_json = base64.urlsafe_b64decode(state_encoded.encode()).decode()
    return json.loads(state_json)

@app.get("/slack_auth")
async def slack_auth():
    try:
        authorization_url, state, code_verifier = slackconnector.get_slack_authorization_url()
        session_id = os.urandom(16).hex()
        encoded_state = encode_state(state, code_verifier, session_id)
        return JSONResponse(content={"authorization_url": f"{authorization_url}&state={encoded_state}"})
    except Exception as e:
        logger.error(f"Error during slack_auth: {str(e)}")
        raise HTTPException(status_code=500, detail="Error initiating Slack authorization")

@app.get("/slack_callback")
async def slack_callback(request: Request):
    try:
        encoded_state = request.query_params.get('state')
        if not encoded_state:
            logger.error("State not found in the callback request")
            raise HTTPException(status_code=400, detail="Missing state")

        decoded_state = decode_state(encoded_state)
        state = decoded_state['state']
        code_verifier = decoded_state['code_verifier']
        session_id = decoded_state['session_id']

        logger.info(f"Decoded state: {decoded_state}")

        code = request.query_params.get('code')
        if not code:
            logger.error("Missing code in the callback request")
            raise HTTPException(status_code=400, detail="Missing code")

        try:
            token = slackconnector.fetch_slack_token(code, state, code_verifier)
            logger.info(f"Slack Token: {token}")

            # Process files and chat history from Slack
            await slackconnector.process_files_and_chats(token)

            return JSONResponse(content={"status": "success", "message": "Slack authorization successful"})
        except Exception as e:
            logger.error(f"Error fetching Slack token or processing data: {str(e)}")
            raise HTTPException(status_code=500, detail="Error fetching Slack token or processing data")

    except Exception as e:
        logger.error(f"Error in slack_callback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/downloads/{filename}")
async def download_file(filename: str):
    return FileResponse(f"{DOWNLOAD_DIR}/{filename}")

@app.get("/downloads/preview/{filename}")
async def preview_file(filename: str):
    file_path = f"{DOWNLOAD_DIR}/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    preview_path = f"{DOWNLOAD_DIR}/previews/{filename}.png"
    os.makedirs(os.path.dirname(preview_path), exist_ok=True)

    # Convert Office files to PDF first
    if filename.endswith(('.docx', '.pptx', '.xlsx')):
        pdf_path = file_path.rsplit('.', 1)[0] + '.pdf'
        subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", os.path.dirname(file_path), file_path], check=True)
        file_path = pdf_path  # Update file_path to the new PDF

    # Convert PDF to PNG
    if filename.endswith(('.pdf', '.docx', '.pptx', '.xlsx')):
        images = convert_from_path(file_path, first_page=0, last_page=1)
        images[0].save(preview_path, 'PNG')
    elif filename.endswith(('.jpg', '.jpeg', '.png', '.gif')):
        return FileResponse(file_path)
    elif filename.endswith('.txt'):
        with open(file_path, 'r') as file:
            text = file.read(500)
        img = Image.new('RGB', (800, 600), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        d.text((10, 10), text, font=font, fill=(0, 0, 0))
        img.save(preview_path, 'PNG')
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    return FileResponse(preview_path)

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
