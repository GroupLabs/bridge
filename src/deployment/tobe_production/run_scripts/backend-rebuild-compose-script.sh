#!/bin/bash

# Navigate to the src/backend directory to build the Docker image
cd ../backend
docker build -t api .

# Navigate to the src/deployment directory to manage docker-compose
cd ../deployment

# Check if docker-compose is already running
if docker-compose ps -q | grep -q '.'; then
  echo "\n\ndocker-compose is up. Restarting api service.\n\n"
  docker-compose up -d --no-deps --force-recreate api
else
  echo "\n\ndocker-compose is down. Starting all services.\n\n"
  docker-compose up -d
fi

echo "success"
