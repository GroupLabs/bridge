from fastapi import Depends, FastAPI
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
import yaml

from serverutils import Health, Status, Query
from postgres import create_node
from searchutils import Search
from correlationutils import simple_correlation

s = Search()

PROD = True

config_path = 'config/db_config.yaml'

def load_config(path: str):
    with open(path, 'r') as file:
        config = yaml.safe_load(file)
    return config

# https://fastapi.tiangolo.com/advanced/events/
@asynccontextmanager
async def lifespan(app: FastAPI):

    db_config = load_config(config_path)

    for db in db_config['databases']:
        print("Loading: " + db["dbname"])

        if not os.path.isdir(db["dbname"]):
            print("...creating node")
            create_node(db["dbname"], db["user"])
        # add_semantic_information()

        print("...semantic storing")
        # store for semantic search
        for file in os.listdir(db["dbname"]):
            filepath = os.path.join(db["dbname"], file)
            # check if file is yaml/ not a directory
            if file.endswith('.yaml') and os.path.isfile(filepath):
                with open(filepath, 'r') as f:
                    data = yaml.safe_load(f)
                    s.store_object(data[file.split(".")[0]])
                    print("...stored: " + file.split(".")[0])

        print("...building adjacency list")
        # generate adjacency list
        adjacency_list = {}

        for file in os.listdir(db["dbname"]):
            data = {}
            # Construct the full file path
            filepath = os.path.join(db["dbname"], file)
            # Check if the file is a YAML file and it's not a directory
            if file.endswith('.yaml') and os.path.isfile(filepath):
                filename = file.split(".")[0]

                with open(filepath, 'r') as f:
                    data = yaml.safe_load(f)

                    adjacency_list[filename] = data[filename]["related_tables"]


    yield
    # free_db(dbconn)
    # free resources
    # telemetry?

    print("Exit Process")

app = FastAPI(lifespan=lifespan)












@app.get("/health-check")
async def health_res():
    return {"health": health}



@app.post("/simple-corr")
async def simple_corr(input: Query):

    target = s.query(input.query)

    corr = simple_correlation(target)

    return {"health": health, "t" : target, "corr" : corr}









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