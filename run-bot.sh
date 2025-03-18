#!/bin/bash

# Create logs directory if it doesn't exist
echo "Creating logs directory..."
mkdir -p "$(pwd)/logs" "$(pwd)/vector_db"

# Check if Ollama is running
echo "Checking if Ollama is running..."
if ! docker ps | grep -q ollama; then
    echo "Starting Ollama container..."
    docker start ollama || docker run -d --name ollama -p 11434:11434 ollama/ollama
    sleep 5  # Give it time to start
fi

# Stop and remove existing container if it exists
echo "Cleaning up previous containers..."
docker stop orcha-telegram-bot 2>/dev/null || true
docker rm orcha-telegram-bot 2>/dev/null || true

# Build the Docker image (WITH cache to save time)
echo "Building Docker image..."
docker build -t orcha-bot . || { echo "Build failed!"; exit 1; }

# Run the container with environment variables and network host mode
echo "Starting bot container..."
docker run -d \
  --name orcha-telegram-bot \
  --env-file .env \
  --network=host \
  --mount type=bind,source="$(pwd)/logs",target=/app/logs \
  --mount type=bind,source="$(pwd)/vector_db",target=/app/vector_db \
  orcha-bot

# Show logs
echo "Bot is starting. Showing logs:"
docker logs -f orcha-telegram-bot