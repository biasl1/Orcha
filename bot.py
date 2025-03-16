from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import os
import logging
import datetime
from dotenv import load_dotenv
from models.llm_handler import process_query, schedule_random_surreal_message

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Create a separate logger for user interactions
os.makedirs('logs', exist_ok=True)
user_logger = logging.getLogger('user_interactions')
user_logger.setLevel(logging.INFO)
user_handler = logging.FileHandler('logs/user_messages.log')
user_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
user_logger.addHandler(user_handler)

# Load environment variables from .env file
load_dotenv()

def start(update: Update, context: CallbackContext) -> None:
    # Log the start command
    user = update.effective_user
    user_logger.info(f"User {user.id} ({user.username}) started the bot")
    update.message.reply_text("Hello! I'm Orcha, your personal secretary. What can I do for you?")

def send_telegram_message(chat_id, text):
    """Send a message to a specific Telegram chat"""
    # We'll use the global updater object to send messages
    updater.bot.send_message(chat_id=chat_id, text=text)

def handle_message(update: Update, context: CallbackContext) -> None:
    """Process user messages and respond using the LLM."""
    user_message = update.message.text
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Log the user's message
    user_logger.info(f"User {user.id} ({user.username}): {user_message}")
    
    # Schedule a random surreal message for this user
    schedule_random_surreal_message(str(chat_id), send_telegram_message)
    
    # No "Processing..." message - like a human!
    
    # Get response from LLM
    response = process_query(user_message)
    update.message.reply_text(response)
    
    # Log the bot's response
    user_logger.info(f"Bot to {user.id}: {response[:100]}...")

def main():
    # Get token from environment variable
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set!")
        return
    
    global updater
    updater = Updater(token)
    dp = updater.dispatcher

    # Add handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    print("Bot is running!")
    user_logger.info("Bot started successfully")
    updater.idle()

if __name__ == "__main__":
    main()