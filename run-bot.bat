@echo off
REM filepath: /Users/test/Documents/development/Task_Management/Orcha/run-bot.bat

REM Create logs directory if it doesn't exist
echo Creating logs directory...
if not exist logs mkdir logs

REM Check if Ollama is running (Windows Docker)
echo Checking if Ollama is running...
docker ps | findstr ollama
if %ERRORLEVEL% NEQ 0 (
    echo Starting Ollama container...
    docker start ollama || docker run -d --name ollama -p 11434:11434 ollama/ollama
    timeout /t 5
)

REM Stop and remove existing container if it exists
echo Cleaning up previous containers...
docker stop orcha-telegram-bot 2>nul
docker rm orcha-telegram-bot 2>nul

REM Build the Docker image from scratch (no cache)
echo Building Docker image...
docker build --no-cache -t orcha-bot . || (echo Build failed! & exit /b 1)

REM Run the container with environment variables
echo Starting bot container...
docker run -d ^
  --name orcha-telegram-bot ^
  --env-file .env ^
  --link ollama ^
  --mount type=bind,source="%CD%\logs",target=/app/logs ^
  orcha-bot

REM Show logs
echo Bot is starting. Showing logs:
docker logs -f orcha-telegram-bot