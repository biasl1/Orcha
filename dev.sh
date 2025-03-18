#!/bin/bash

# Fast development mode with Docker only for Ollama
mkdir -p logs vector_db

# Set environment variable from .env
export $(grep -v '^#' .env | xargs)

# Make sure Docker Ollama is running
if ! docker ps | grep -q ollama; then
  echo "Starting Ollama in Docker..."
  docker start ollama || docker run -d --name ollama -p 11434:11434 ollama/ollama
  sleep 5
fi

# Update LLM_HANDLER to use Docker container
sed -i.bak 's/host = "ollama"/host = "localhost"/g' models/llm_handler.py

# Run the bot directly
echo "Starting bot..."
python bot.py