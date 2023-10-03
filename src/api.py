from fastapi import FastAPI
import os
from dotenv import load_dotenv

from lakehouse.storage import Storage

load_dotenv()

app = FastAPI()
storage = Storage(vec_store_loadfile=os.getenv('STORAGE'))

@app.get("/health-check")
async def health_res():
    return {"health": "healthy"}

@app.post("/query")
async def health_res(input):
    
    a = storage.vec_store.query("How many players are in a game?")
    
    
    return {"health": a}

if __name__ == "__main__":
    import uvicorn
    
    PORT = 8000

    if not os.getenv('ENV'):
        print("Missing environment variable.")
        exit(1)

    if os.getenv('ENV') == "DEBUG":
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try: 
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]

            print("\n\nServer available @ http://" + ip_address + ":" + str(PORT) + "\n\n")
        except OSError as e:
            print(e)

    if os.getenv('ENV') == "PROD":
        print("Please consider the following command to start the server:")
        print("\t EXPERIMENTAL: uvicorn your_app_module:app --workers 3")

    uvicorn.run(app, host="0.0.0.0", port=PORT)