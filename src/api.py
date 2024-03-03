from fastapi import Depends, FastAPI
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

from storage import Storage
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
s = Storage()

@app.get("/health-check")
async def health_res():
    return {"health": health, "num loaded": len(s)}

# load collection (dir)/document (pdf, txt) or database (postgres, mssql, duckdb)/table (csv, tsv, parquet)
# accepts path to data (unstructurded | structured)
# returns ok

@app.post("/load")
async def load(input: Load):

    s.load_data(input.filepath)

    return {"health": health, "status" : "success"}

# search
# accepts NL query
# returns distance

@app.get("/query")
async def query(input: Query):

    out = s.query(input.query)

    if input.use_llm:
        pass

    return {"health": health, "status" : "success", "out" : out}





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