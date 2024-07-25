from fastapi import FastAPI, HTTPException, Body, Query
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import requests
from fastapi.middleware.cors import CORSMiddleware
import math
from typing import List, Dict
import random
from pprint import pprint

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Specify the correct origins as per your requirements
    allow_credentials=True,
    allow_methods=["*"],  # This allows all methods including OPTIONS
    allow_headers=["*"],
)

# Load the Sentence Transformer model
model = SentenceTransformer('intfloat/multilingual-e5-large-instruct')
model.max_seq_length = 4096  # Adjust the maximum sequence length if necessary

# Define the task description
task = 'Given a web search query, retrieve relevant passages that answer the query'

# Helper function for detailed instructions
def get_detailed_instruct(task_description: str, query: str) -> str:
    return f'Instruct: {task_description}\nQuery: {query.lower()}'

# Define the catalog with lowercase keys
catalog = {
    "dryer": 520.00,
    "washing machine": 800.00,
    "dishwasher": 450.00,
    "electric stove": 600.00,
    "refrigerator": 1200.00,
    "freezer": 780.00,
    "microwave oven": 150.00,
    "blender": 90.00,
    "toaster": 30.00,
    "coffee maker": 85.00,
    "air conditioner": 350.00,
    "heater": 110.00,
    "ceiling fan": 120.00,
    "sink": 200.00,
    "faucet": 75.00,
    "shower head": 45.00,
    "toilet": 250.00,
    "bathtub": 400.00,
    "bathroom cabinet": 220.00,
    "kitchen cabinet": 300.00,
    "range hood": 250.00,
    "light fixture": 45.00,
    "led bulbs": 15.00,
    "water heater": 480.00,
    "garbage disposal": 130.00,
    "humidifier": 70.00,
    "dehumidifier": 180.00,
    "air purifier": 200.00,
    "induction cooktop": 430.00,
    "vacuum cleaner": 150.00
}

# Pre-compute embeddings for catalog descriptions with detailed instruction
catalog_descriptions = [desc.lower() for desc in catalog.keys()]
catalog_queries = [get_detailed_instruct(task, desc) for desc in catalog_descriptions]
catalog_embeddings = model.encode(catalog_queries, convert_to_tensor=True, normalize_embeddings=True)
catalog_embeddings = catalog_embeddings.cpu().detach().numpy()

# Initialize Faiss index for similarity search
dimension = catalog_embeddings.shape[1]
faiss_index = faiss.IndexFlatL2(dimension)
faiss_index.add(catalog_embeddings)

class Item(BaseModel):
    text: str

@app.post("/categorizer/")
async def categorizer(item: Item):

#     You can also include the response from your other service here
    url = "http://localhost:8080/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer no-key"
    }
    data = {
        "model": "LLaMA_CPP",
        "messages": [
            {
                "role": "system",
                "content": "You are a categorizer. Only respond with \"Electrical\", \"Plumbing\", \"Appliance\", or if it does not relate with anything, reply with \"Unknown\""
            },
            {
                "role": "user",
                "content": item.text
            }
        ]
    }

    response = requests.post(url, json=data, headers=headers)
    category = response.json()["choices"][0]["message"]["content"].replace("<|eot_id|>", "")

    query_text = get_detailed_instruct(task, item.text.lower())
    query_embedding = model.encode([query_text], convert_to_tensor=True, normalize_embeddings=True)
    query_embedding = query_embedding.cpu().detach().numpy()
    
    # Search in Faiss index for the top matching catalog items
    D, I = faiss_index.search(query_embedding, k=len(catalog_descriptions))  # Search among all items
    
    results = []
    prices = []
    for idx, distance in zip(I[0], D[0]):
        similarity = (1 - np.sqrt(distance / 2)) * 100  # Convert distance to similarity
        if similarity >= 99.0:
            item_description = catalog_descriptions[idx]
            item_price = catalog[item_description]
            results = [{
                "item": item_description,
                "price": f"${item_price:.2f}",
                "similarity": f"{similarity:.2f}%"
            }]
            pprint(results)
            return {
                "query": item.text,
                "results": sorted(results, key=lambda x: float(x['similarity'].rstrip('%')), reverse=True),
                "price": f"${item_price:.2f}",
                "category" : category
            }
        elif similarity >= 62.0:  # Apply the 80% similarity threshold
            item_description = catalog_descriptions[idx]
            item_price = catalog[item_description]
            results.append({
                "item": item_description,
                "price": f"${item_price:.2f}",
                "similarity": f"{similarity:.2f}%"
            })
            prices.append(item_price)

    print(results)
    
    # Calculate average price if there are any results
    average_price = np.mean(prices) if prices else 0

    if average_price == 0:
        average_price = "-"
    else:
        average_price = f"${average_price:.2f}"

    res = {
        "query": item.text,
        "results": sorted(results, key=lambda x: float(x['similarity'].rstrip('%')), reverse=True),
        "price": average_price,
        "category" : category
    }

    pprint(res)
    return res








if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)