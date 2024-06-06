import os
import json
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from fastapi import Depends, FastAPI, Response, File, UploadFile, Form, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse, JSONResponse, FileResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import subprocess
import time
from log import setup_logger
from storage import load_data, load_model, query, get_inference, sort_docs
from serverutils import Health, Status, Load, Query
from serverutils import ChatRequest
from ollama import chat, gen
from config import config
from integration_layer import parse_config_from_string
from integration_layer import prepare_inputs_for_model
from integration_layer import format_model_inputs
from elasticutils import Search  # Import the Search class
from starlette.middleware.sessions import SessionMiddleware

# Load environment variables
load_dotenv()

TEMP_DIR = config.TEMP_DIR
DOWNLOAD_DIR = "downloads"
SCOPES = ['https://www.googleapis.com/auth/drive.file']
CLIENT_SECRET_FILE = os.getenv('CLIENT_SECRET_FILE')

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

@app.post("/sort")
async def sort_docs_ep(type: str=Form(...)):
    type_of_sort = ["name", "size", "type", "created"]
    if type not in type_of_sort:
        return "invalid sort"

    return sort_docs(type)

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
        response_message = gen(chat_request.message)  # Assume gen returns a string
        async_generator = string_to_async_generator(response_message)

        search.save_chat_to_history(chat_request.id, chat_request.message, response_message, user_id)
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
