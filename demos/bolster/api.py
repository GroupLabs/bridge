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
    "LED bulbs": 15.00,
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
        elif similarity >= 60.0:  # Apply the 80% similarity threshold
            item_description = catalog_descriptions[idx]
            item_price = catalog[item_description]
            results.append({
                "item": item_description,
                "price": f"${item_price:.2f}",
                "similarity": f"{similarity:.2f}%"
            })
            prices.append(item_price)
    
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










class Job(BaseModel):
    title: str
    latitude: float
    longitude: float
    description: str

class JobWithID(Job):
    id: int
    price: float

class SimilarJobsResponse(BaseModel):
    selected_job: JobWithID
    similar_jobs: List[JobWithID]
    average_price: float

jobs_db = [
    JobWithID(id=1, title="Kitchen Renovation", latitude=51.0447, longitude=-114.0719, price=25000, description="Complete kitchen remodel including new cabinets, countertops, and appliances."), # Calgary
    JobWithID(id=2, title="Roof Replacement", latitude=51.1625, longitude=-114.0897, price=15000, description="Full roof replacement with high-quality shingles."), # Cochrane
    JobWithID(id=3, title="Bathroom Remodel", latitude=51.0833, longitude=-114.2014, price=12000, description="Modern bathroom renovation with new fixtures and tiling."), # Airdrie
    JobWithID(id=4, title="House Painting", latitude=51.1521, longitude=-114.3751, price=8000, description="Exterior house painting for a two-story home."), # Bragg Creek
    JobWithID(id=5, title="Deck Construction", latitude=51.0449, longitude=-114.0715, price=10000, description="Build a new 300 sq ft wooden deck with railings."), # Calgary
    JobWithID(id=6, title="Garage Build", latitude=51.0835, longitude=-114.2012, price=20000, description="Construct a new two-car garage."), # Airdrie
    JobWithID(id=7, title="Fence Installation", latitude=51.0448, longitude=-114.0720, price=7000, description="Install a new wooden fence around the property."), # Calgary
    JobWithID(id=8, title="Basement Finishing", latitude=51.1627, longitude=-114.0898, price=30000, description="Finish the basement with new flooring and drywall."), # Cochrane
    JobWithID(id=9, title="Landscape Design", latitude=51.1523, longitude=-114.3750, price=15000, description="Complete landscape design including new plants and walkways."), # Bragg Creek
    JobWithID(id=10, title="Window Replacement", latitude=51.0446, longitude=-114.0721, price=12000, description="Replace all windows in the house with energy-efficient models."), # Calgary
    JobWithID(id=11, title="Driveway Paving", latitude=51.0832, longitude=-114.2013, price=20000, description="Pave the driveway with asphalt."), # Airdrie
    JobWithID(id=12, title="Patio Installation", latitude=51.1626, longitude=-114.0896, price=14000, description="Install a new stone patio in the backyard."), # Cochrane
    JobWithID(id=13, title="Interior Renovation", latitude=51.0445, longitude=-114.0718, price=35000, description="Complete interior renovation including flooring and walls."), # Calgary
    JobWithID(id=14, title="Swimming Pool Construction", latitude=51.0446, longitude=-114.0717, price=50000, description="Construct a new in-ground swimming pool."), # Calgary
    JobWithID(id=15, title="Solar Panel Installation", latitude=51.0834, longitude=-114.2011, price=25000, description="Install solar panels on the roof."), # Airdrie
    JobWithID(id=16, title="Home Extension", latitude=51.1624, longitude=-114.0899, price=60000, description="Add a new room extension to the house."), # Cochrane
    JobWithID(id=17, title="Plumbing Upgrade", latitude=51.0447, longitude=-114.0722, price=12000, description="Upgrade the plumbing system throughout the house."), # Calgary
    JobWithID(id=18, title="Electrical Rewiring", latitude=51.0835, longitude=-114.2015, price=15000, description="Rewire the electrical system in the house."), # Airdrie
    JobWithID(id=19, title="Attic Insulation", latitude=51.1626, longitude=-114.0895, price=7000, description="Add insulation to the attic for better energy efficiency."), # Cochrane
    JobWithID(id=20, title="Porch Renovation", latitude=51.1522, longitude=-114.3752, price=18000, description="Renovate the porch area with new materials."), # Bragg Creek
    JobWithID(id=21, title="Hardwood Flooring", latitude=51.0449, longitude=-114.0723, price=22000, description="Install new hardwood flooring throughout the house."), # Calgary
    JobWithID(id=22, title="Gutter Installation", latitude=51.0448, longitude=-114.0724, price=5000, description="Install new gutters and downspouts."), # Calgary
    JobWithID(id=23, title="Chimney Repair", latitude=51.1625, longitude=-114.0894, price=12000, description="Repair and reinforce the chimney structure."), # Cochrane
    JobWithID(id=24, title="Custom Shelving", latitude=51.0832, longitude=-114.2016, price=8000, description="Build and install custom shelving units."), # Airdrie
    JobWithID(id=25, title="Septic System Installation", latitude=51.1520, longitude=-114.3753, price=30000, description="Install a new septic system for the property."), # Bragg Creek
]

jobs_db += [
    JobWithID(id=26, title="Kitchen Upgrade", latitude=51.0450, longitude=-114.0725, price=26000, description="Upgrade kitchen with new cabinets, countertops, and modern appliances."), # Calgary
    JobWithID(id=27, title="Roof Shingle Replacement", latitude=51.1628, longitude=-114.0900, price=15500, description="Replace old roof shingles with high-quality new ones."), # Cochrane
    JobWithID(id=28, title="Bathroom Overhaul", latitude=51.0836, longitude=-114.2017, price=12500, description="Complete bathroom overhaul with new tiles and fixtures."), # Airdrie
    JobWithID(id=29, title="Exterior House Painting", latitude=51.1524, longitude=-114.3754, price=8500, description="Paint the exterior of a two-story house."), # Bragg Creek
    JobWithID(id=30, title="Deck Building", latitude=51.0445, longitude=-114.0726, price=10500, description="Construction of a 350 sq ft wooden deck with railings."), # Calgary
    JobWithID(id=31, title="Garage Construction", latitude=51.0837, longitude=-114.2018, price=21000, description="Build a new two-car garage from scratch."), # Airdrie
    JobWithID(id=32, title="Fence Setup", latitude=51.0446, longitude=-114.0727, price=7500, description="Set up a new wooden fence around the yard."), # Calgary
    JobWithID(id=33, title="Basement Renovation", latitude=51.1629, longitude=-114.0901, price=31000, description="Complete basement renovation with new flooring and walls."), # Cochrane
    JobWithID(id=34, title="Garden Landscaping", latitude=51.1525, longitude=-114.3755, price=15500, description="Design and install a new garden landscape including walkways."), # Bragg Creek
    JobWithID(id=35, title="Energy-efficient Window Installation", latitude=51.0448, longitude=-114.0728, price=12500, description="Install energy-efficient windows throughout the house."), # Calgary
    JobWithID(id=36, title="Asphalt Driveway", latitude=51.0838, longitude=-114.2019, price=20500, description="Pave the driveway with durable asphalt."), # Airdrie
    JobWithID(id=37, title="Stone Patio Setup", latitude=51.1627, longitude=-114.0902, price=14500, description="Install a new stone patio in the backyard."), # Cochrane
    JobWithID(id=38, title="Home Interior Makeover", latitude=51.0449, longitude=-114.0729, price=36000, description="Complete makeover of the home's interior, including new floors and walls."), # Calgary
    JobWithID(id=39, title="In-ground Pool Installation", latitude=51.0450, longitude=-114.0730, price=51000, description="Install a new in-ground swimming pool in the backyard."), # Calgary
    JobWithID(id=40, title="Rooftop Solar Panels", latitude=51.0839, longitude=-114.2020, price=25500, description="Install rooftop solar panels for energy efficiency."), # Airdrie
]



# Define the range for latitude and longitude adjustment
adjustment_range = 0.05

# Function to randomly adjust latitude and longitude
def adjust_lat_long(lat, long):
    new_lat = lat + random.uniform(-adjustment_range, adjustment_range)
    new_long = long + random.uniform(-adjustment_range, adjustment_range)
    return new_lat, new_long


for job in jobs_db:
    job.latitude, job.longitude = adjust_lat_long(job.latitude, job.longitude)

# Pre-compute embeddings for job descriptions
job_descriptions = [job.description.lower() for job in jobs_db]
job_embeddings = model.encode(job_descriptions, convert_to_tensor=True, normalize_embeddings=True)
job_embeddings = job_embeddings.cpu().detach().numpy()

# Initialize Faiss index for similarity search
dimension = job_embeddings.shape[1]
faiss_index = faiss.IndexFlatL2(dimension)
faiss_index.add(job_embeddings)



def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0  # Radius of the Earth in kilometers
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance

@app.post("/jobs", response_model=JobWithID)
def create_job(job: Job, distance_threshold: float = Query(50.0)):
    job_description = job.description.lower()
    job_embedding = model.encode([job_description], convert_to_tensor=True, normalize_embeddings=True)
    job_embedding = job_embedding.cpu().detach().numpy()

    # Search in Faiss index for the top matching jobs
    D, I = faiss_index.search(job_embedding, k=len(job_descriptions))  # Search among all jobs
    
    similar_jobs = []
    for idx, distance in zip(I[0], D[0]):
        similarity = (1 - np.sqrt(distance / 2)) * 100  # Convert distance to similarity
        candidate_job = jobs_db[idx]
        distance_to_candidate = haversine_distance(job.latitude, job.longitude, candidate_job.latitude, candidate_job.longitude)
        if similarity >= 60.0 and distance_to_candidate <= distance_threshold:  # Apply similarity and distance threshold
            similar_jobs.append(candidate_job)

    pprint(similar_jobs)

    # Calculate the average price of similar jobs
    if similar_jobs:
        average_price = sum(job.price for job in similar_jobs) / len(similar_jobs)
    else:
        average_price = 0  # Default to 0 if no similar jobs are found

    job_with_id = JobWithID(id=len(jobs_db) + 1, price=average_price, **job.dict())
    jobs_db.append(job_with_id)

    # Update the Faiss index with the new job
    job_descriptions.append(job_description)
    faiss_index.add(job_embedding)

    return job_with_id

@app.get("/jobs", response_model=List[JobWithID])
def get_jobs():
    return jobs_db

@app.get("/jobs/{job_id}/similar", response_model=SimilarJobsResponse)
def get_similar_jobs(job_id: int, distance_threshold: float = Query(50.0)):
    selected_job = next((job for job in jobs_db if job.id == job_id), None)
    if not selected_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    similar_jobs = [
        job for job in jobs_db 
        if job.id != selected_job.id 
        and haversine_distance(selected_job.latitude, selected_job.longitude, job.latitude, job.longitude) <= distance_threshold
    ]
    
    # Calculate the average price of similar jobs
    if similar_jobs:
        average_price = sum(job.price for job in similar_jobs) / len(similar_jobs)
    else:
        average_price = 0  # Default to 0 if no similar jobs are found

    return SimilarJobsResponse(selected_job=selected_job, similar_jobs=similar_jobs, average_price=average_price)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)