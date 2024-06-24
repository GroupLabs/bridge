#!/bin/bash

# Step 1: Bring down the Docker containers
docker compose down

# Step 2: Move up 2 directories, then into the backend directory
cd ../../backend

# Step 3: Build the Docker image with the tag 'api'
docker build -t api .

# Step 4: Move into the 'deployment/production' directory
cd ../deployment/production

# Step 5: Bring up the Docker containers in detached mode
docker compose up -d
