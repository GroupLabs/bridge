from fastapi import Depends, FastAPI
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

from storage import load_data, query
from serverutils import Health, Status, Load, Query


PROD = True

# https://fastapi.tiangolo.com/advanced/events/
@asynccontextmanager
async def lifespan(app: FastAPI):

    yield
    # free_db(dbconn)
    # free resources
    # telemetry?

    print("Exit Process")

app = FastAPI(lifespan=lifespan)

@app.get("/health-check")
async def health_endpoint():
    return {"health": health}

@app.get("/task/{task_id}/status")
async def get_task_status(task_id: str):
    task = load_data.AsyncResult(task_id)
    return {"task_id": task_id, "status": task.state}

@app.get("/task/{task_id}/result")
async def get_task_result(task_id: str):
    task = load_data.AsyncResult(task_id)
    if task.state == 'SUCCESS':
        result = task.get(timeout=1)
        return {"task_id": task_id, "status": task.state, "result": result}
    return {"task_id": task_id, "status": task.state}

# load collection (dir)/document (pdf, txt) or database (postgres, mssql, duckdb)/table (csv, tsv, parquet)
# accepts path to data (unstructurded | structured)
# returns ok

@app.post("/load")
async def load_endpoint(input: Load):
    try:
        task = load_data.delay(input.filepath)
        return {"status": "success", "task_id": task.id}
    except NotImplementedError:
        return {"health": health, "status" : "fail", "reason" : "file type not implemented"}
    

# search
# accepts NL query
# returns distance

@app.get("/query")
async def query_endpoint(input: Query):

    resp = query(input.query)

    if input.use_llm:
        context_list = [x["fields"]["text"] for x in resp.hits]

        prompt = f"{input.query}\n"
        prompt += "Use the following for context:\n"
        prompt += " ".join(context_list)

    return {"health": health, "status" : "success", "resp" : [x["fields"]["text"] for x in resp.hits]}





if __name__ == "__main__":
    import uvicorn

    load_dotenv()
    
    PORT = 8000
    
    # if os.getenv('PORT'):
    #     PORT = int(os.getenv('PORT'))

    # if not os.getenv('ENV'):
    #     print("Missing environment variable.")
    #     exit(1)
    
    # if not os.getenv('API_KEY'):
    #     print("Missing API key.")
    #     exit(1)

    # if os.getenv('ENV') == "DEBUG":
    #     import socket

    #     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    #     try: 
    #         s.connect(("8.8.8.8", 80))
    #         ip_address = s.getsockname()[0]

    #         print("\n\nServer available @ http://" + ip_address + ":" + str(PORT) + "\n\n")
    #     except OSError as e:
    #         print(e)

    # if os.getenv('ENV') == "PROD":
    #     print("Please consider the following command to start the server:")
    #     print("\t EXPERIMENTAL: uvicorn your_app_module:app --workers 3")
        
    global health 
    health = Health(status=Status.OK, ENV=os.getenv('ENV'))
    uvicorn.run(app, host="0.0.0.0", port=PORT)