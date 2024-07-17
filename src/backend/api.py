from fastapi import FastAPI, Form, Response, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from log import setup_logger
from storage import load_data, query, retrieve_object_ids
from serverutils import Health, Status,Query

import json

from config import config

TEMP_DIR = config.TEMP_DIR
TASK_ID_FILE = 'task_ids.json'

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

# Endpoints for debugging
if config.ENV == "DEBUG":
    from debug import router as debug_router
    app.include_router(debug_router)

origins = [
    "http://localhost:3000",  # Add the origin(s) you want to allow
    "*"
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

@app.get("/health")
async def health_endpoint():
    return {"health": health}


@app.get("/task/{task_id}")
async def get_task_result(task_id: str):
    # note: no point adding a progress bar, the longest part (unstructured) is opaque

    task = load_data.AsyncResult(task_id)

    # return result obj
    # if task.state == 'SUCCESS':
    #     result = task.get(timeout=1)
    #     return {"task_id": task_id, "status": task.state, "result": result}

    return {"task_id": task_id, "status": task.state}

@app.get("/integrations")
async def get_all_integration():
    tasks = []

    # Read task ids from the task ids file
    if os.path.exists(TASK_ID_FILE):
        with open(TASK_ID_FILE, 'r') as file:
            tasks = json.load(file)

    task_states = []
    for task_id in tasks:
        task = load_data.AsyncResult(task_id["task_id"])

        if task.state == 'SUCCESS':
            result = task.get(timeout=1)
            task_states.append({"task_id": task_id["task_id"], "status": task.state, "filename": task_id["filename"], "type": result})
        else:
            task_states.append({"task_id": task_id["task_id"], "status": task.state, "filename": task_id["filename"]})

    return {"tasks": task_states}

@app.get("/retrieve_ids/{index}")
async def retrieve_all(index: str):
    return {"health": health, "status" : "success", "ids" : retrieve_object_ids(index)}

# load collection (dir)/document (pdf, txt) or database (postgres, mssql, duckdb)/table (csv, tsv, parquet)
# accepts path to data (unstructurded | structured)
# returns ok

@app.post("/load")
async def load_data_ep(response: Response, file: UploadFile = File(...), c_type: str = Form(None)):
    try:
        os.makedirs(TEMP_DIR, exist_ok=True)

        temp_file_path = os.path.join(TEMP_DIR, file.filename)
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(await file.read())

        task = load_data.delay(temp_file_path, file.filename, c_type)

        # Read existing tasks
        if os.path.exists(TASK_ID_FILE):
            with open(TASK_ID_FILE, 'r') as f:
                try:
                    tasks = json.load(f)
                except json.JSONDecodeError:
                    tasks = []
        else:
            tasks = []

        # Append new task
        tasks.append({"task_id": task.id, "filename": file.filename})

        with open(TASK_ID_FILE, 'w') as f:
            json.dump(tasks, f)

        response.status_code = 202
        logger.info(f"LOAD accepted: {file.filename}")
        return {"status": "accepted", "task_id": task.id}
    except NotImplementedError:
        logger.warning(f"LOAD incomplete: {file.filename}")
        response.status_code = 400
        return {"health": "ok", "status": "fail", "reason": "file type not implemented"}
    
# search
# accepts NL query
# returns distance

@app.post("/query")
async def nl_query(input: Query):

    resp = query(input.query, input.index, input.doc_id)

    if input.use_llm:
        # context_list = [x["fields"]["text"] for x in resp.hits] this is for vespa, need to switch to es

        prompt = f"{input.query}\n"
        prompt += "Use the following for context:\n"
        # prompt += " ".join(context_list) this is for vespa, need to switch to es

    logger.info(f"QUERY success: {input.query}")

    return {"health": health, "status" : "success", "query" : input.query, "resp" : resp}

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
