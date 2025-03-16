# Orcha - Your AI Secretary

Orcha is a Telegram chatbot that acts as a personal assistant, powered by locally running LLMs through Ollama. The bot sends surreal German messages at random intervals and responds to user queries using the Llama2 language model.

## Current Features
- AI-powered responses to user questions via Ollama and Llama2
- Random surreal German messages at intervals (Brotsalad Almus and Nachtsteine)
- Comprehensive user interaction logging
- Docker containerization for easy deployment
- Cross-platform support (macOS, Linux, Windows)

## Tech Stack
- **Programming Language:** Python 3.10
- **Framework:** python-telegram-bot
- **LLM:** Ollama with Llama2
- **Containerization:** Docker
- **Logging:** Standard Python logging

## Installation

### Prerequisites
- Docker installed ([Get Docker](https://www.docker.com/get-started))
- Telegram Bot token (get from [@BotFather](https://t.me/botfather))

### Setup

1. **Clone this repository:**
   ```
   git clone https://github.com/yourusername/orcha.git
   cd orcha
   ```

2. **Configure environment variables:**
   Create a 

.env

 file with your Telegram Bot token:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   ```

### Running on macOS/Linux

Run the provided shell script:
```
chmod +x run-bot.sh
./run-bot.sh
```

### Running on Windows

Run the provided batch script:
```
run-bot.bat
```

## Local Development Setup

To run without Docker:

1. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   ```
   # On Linux/macOS
   export TELEGRAM_BOT_TOKEN=your_token_here
   
   # On Windows
   set TELEGRAM_BOT_TOKEN=your_token_here
   ```

3. **Start the Ollama service**
   Download from [ollama.ai](https://ollama.ai) and install

4. **Pull the llama2 model:**
   ```
   ollama pull llama2
   ```

5. **Run the bot:**
   ```
   python bot.py
   ```

## Future Plans
- Google Calendar integration for scheduling
- Task tracking and milestone management
- Advanced procrastination prevention
- Multi-agent coordination for team orchestration

## Contributing
Pull requests and issues are welcome! Feel free to contribute to this project.

## License
MIT License