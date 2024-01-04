from fastapi import FastAPI
import os
from dotenv import load_dotenv

from serverutils import Query

from lakehouse.storage import Storage
from data_engine.engine import llm, decode_code, decode_files

load_dotenv()

app = FastAPI()
storage = Storage(vec_store_loadfile=os.getenv("STORAGE"))


@app.get("/health-check")
async def health_res():
    return {"health": "healthy"}


@app.post("/query")
async def query(input: Query):
    if not input.model:
        model = "gpt-4"
    else:
        model = input.model

    out = storage.vec_store.query(input.query)

    out = decode_files(out)

    prompt = f"{input.query} Write python code and save the answer in a variable 'OUTPUT'. The relevant information is {out} Not all information is relevant. Remember to save the answer in OUTPUT."

    llm_raw = llm(prompt, model=model)

    llm_out = decode_code(llm_raw)

    return {"model": model, "prompt": prompt, "raw": llm_raw, "output": llm_out}


@app.post("/debug/query-all-models")
async def query(input: Query):
    models = ["zephyr", "llama2", "mistral", "codeup", "gpt-4", "codellama:13b"]

    resp = {}

    for model in models:
        out = storage.vec_store.query(input.query)

        out = decode_files(out)

        prompt = f"{input.query} Write python code and save the answer in a variable 'OUTPUT'. The relevant information is {out}"

        llm_raw = llm(prompt, model=model)

        llm_out = decode_code(llm_raw)

        resp[model] = llm_out

    return {"prompt": prompt, "res": resp}


@app.post("/debug/lakehouse")
async def lakehouse(input: Query):
    out = storage.vec_store.query(input.query)

    out = decode_files(out)

    return {"output": out}


if __name__ == "__main__":
    import uvicorn

    PORT = 8000

    if not os.getenv("ENV"):
        print("Missing environment variable.")
        exit(1)

    if os.getenv("ENV") == "DEBUG":
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]

            print(
                "\n\nServer available @ http://" + ip_address + ":" + str(PORT) + "\n\n"
            )
        except OSError as e:
            print(e)

    if os.getenv("ENV") == "PROD":
        print("Please consider the following command to start the server:")
        print("\t EXPERIMENTAL: uvicorn your_app_module:app --workers 3")

    uvicorn.run(app, host="0.0.0.0", port=PORT)
