import requests
import json
import os
from dotenv import load_dotenv
load_dotenv()

# Replace these with your actual Cube.js API endpoint
API_URL = "http://localhost:4000/cubejs-api/v1/load"

# Your DB credentials (this is NOT a standard way to authenticate with Cube.js)
db_credentials = {
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PWD")
}

headers = {
    "Content-Type": "application/json"
}

query = {
  "measures": [
    "apples.count"
  ]
}

# Include the DB credentials in the request payload
# This assumes you have modified your Cube.js server to handle such credentials,
# which is not recommended for security reasons.
payload = {
    "query": query,
    "db_credentials": db_credentials
}

response = requests.post(API_URL, headers=headers, data=json.dumps(payload))

# Check if the response status code is 200 (OK) before attempting to print the data
if response.status_code == 200:
    data = response.json()["data"]
    print(data)
else:
    print(f"Failed to retrieve data: {response.status_code}")
    print(response.text)
