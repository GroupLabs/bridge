import os
from fastapi import FastAPI, UploadFile, File
from dotenv import load_dotenv
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Initialize LlamaParse
parser = LlamaParse(result_type="markdown")

class QueryRequest(BaseModel):
    query: str

@app.post("/parse")
async def parse_file(file: UploadFile = File(...)):
    # Save uploaded file to disk
    file_location = f"temp/{file.filename}"
    with open(file_location, "wb") as f:
        f.write(file.file.read())

    # Use SimpleDirectoryReader to parse our file
    file_extractor = {".pdf": parser}
    documents = SimpleDirectoryReader(input_files=[file_location], file_extractor=file_extractor).load_data()

    # Remove the temporary file
    os.remove(file_location)

    # Create an index from the parsed markdown
    index = VectorStoreIndex.from_documents(documents)

    # Save index for querying later
    index.save_to_disk("index.json")

    return {"message": "File parsed successfully", "documents": documents}

@app.post("/query")
async def query_document(query_request: QueryRequest):
    # Load the index
    index = VectorStoreIndex.load_from_disk("index.json")

    # Create a query engine for the index
    query_engine = index.as_query_engine()

    # Query the engine
    response = query_engine.query(query_request.query)

    return {"response": response}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)