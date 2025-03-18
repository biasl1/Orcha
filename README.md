# Orcha - Professional AI Assistant

A simple Telegram bot powered by locally-running LLMs through Ollama. Orcha features vector-based memory for contextual awareness, conversation tracking, and professional responses to user queries.

## Features

- **Vector-based memory system** using ChromaDB for long-term context
- 💬 **Conversation tracking** that maintains dialog coherence
- 🤖 **Powered by Llama2** running locally through Ollama
- 📊 **Performance monitoring** with `/stats` command
- 📝 **Comprehensive logging** of all interactions
- 🛡️ **Error handling** with graceful degradation
- 🔒 **Admin-only statistics** for monitoring system performance

## Tech Stack

- **Backend**: Python 3.10
- **Bot Framework**: python-telegram-bot
- **LLM Integration**: Ollama with Llama2
- **Vector Database**: ChromaDB
- **Embeddings**: Sentence-Transformers
- **Containerization**: Docker
- **Configuration**: Environment variables through dotenv

## Architecture

```
┌─────────────────┐      ┌─────────────┐      ┌──────────────┐
│  Telegram Bot   │<─────┤ LLM Handler │<─────┤  Ollama API  │
└────────┬────────┘      └──────┬──────┘      └──────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐      ┌─────────────┐
│ User Messaging  │      │   Memory    │
│    Interface    │      │   System    │
└─────────────────┘      └─────────────┘
```

- **bot.py**: Core Telegram interface
- **models/llm_handler.py**: LLM communication & response processing
- **models/memory_handler.py**: Vector-based memory system

## Installation & Setup

### Prerequisites

- Docker installed ([Get Docker](https://www.docker.com/get-started))
- Telegram Bot token (get from [@BotFather](https://t.me/botfather))

### Quick Start with Docker

1. **Clone this repository:**
   ```bash
   git clone https://github.com/yourusername/orcha.git
   cd orcha
   ```

2. **Create 

.env

 file:**
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   ```

3. **Run with provided script:**
   ```bash
   chmod +x run-bot.sh
   ./run-bot.sh
   ```

### Development Setup

#### Option 1: Virtual Environment (Fast Development)

```bash
# Create virtual environment
python -m venv orcha_venv
source orcha_venv/bin/activate  # On Linux/macOS
orcha_venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt

# Run development script
chmod +x dev.sh
./dev.sh
```

#### Option 2: Local Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variable:**
   ```bash
   export TELEGRAM_BOT_TOKEN=your_token_here
   ```

3. **Install and run Ollama:**
   Download from [ollama.ai](https://ollama.ai) and install
   ```bash
   ollama pull llama2
   ```

4. **Run the bot:**
   ```bash
   python bot.py
   ```

## Usage

1. Start a conversation with your bot on Telegram
2. Send messages to get AI-powered responses
3. The bot maintains context from previous exchanges
4. Authorized users can use `/stats` to monitor performance

## Configuration Options

- **SYSTEM_PROMPT**: Modify in 

llm_handler.py

 to change bot personality
- **ConversationManager max_turns**: Adjust to increase/decrease conversation memory
- **Authorized Users**: Set in 

bot.py

 for access to statistics

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin amazing-feature`
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
```