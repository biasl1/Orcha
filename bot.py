from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import os
import logging
import datetime
from dotenv import load_dotenv
from models.llm_handler import process_query, get_metrics
from models.memory_handler import get_memory
import atexit
import json
from utils.calendar import calendar_system
from utils.reminder_scheduler import reminder_scheduler
from utils.processing import DateTimeExtractor
from datetime import datetime, timedelta
import threading
import time

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


# command handler for calendar
def calendar_command(update: Update, context: CallbackContext) -> None:
    """Handler for /calendar command - shows upcoming events"""
    user = update.effective_user
    user_id = str(user.id)
    user_logger.info(f"User {user_id} requested calendar")
    
    # Get upcoming events
    events = calendar_system.get_upcoming_events(user_id)
    
    if not events:
        update.message.reply_text("You don't have any upcoming events in the next 7 days.")
        return
    
    # Format events list
    message = "📅 *Your upcoming events:*\n\n"
    for event in events:
        event_time = event['timestamp'].strftime("%A, %b %d at %I:%M %p")
        message += f"• {event_time}: *{event['title']}*"
        if event.get('description'):
            message += f"\n  _{event['description']}_"
        message += "\n\n"
    
    update.message.reply_text(message, parse_mode="Markdown")

def start(update: Update, context: CallbackContext) -> None:
    # Log the start command
    user = update.effective_user
    user_logger.info(f"User {user.id} ({user.username}) started the bot")
    update.message.reply_text("Hello! I'm Orcha, your professional AI assistant. How can I help you today?")

def stats_command(update: Update, context: CallbackContext) -> None:
    """Handler for /stats command - shows bot statistics"""
    # Only allow specific users to access stats
    authorized_users = [1720592375, 1473396937]  # Replace with your actual admin user IDs
    
    if update.effective_user.id not in authorized_users:
        update.message.reply_text("Sorry, you're not authorized to view stats.")
        return
    
    metrics = get_metrics()
    formatted_stats = json.dumps(metrics, indent=2)
    update.message.reply_text(f"Current statistics:\n```\n{formatted_stats}\n```", parse_mode="Markdown")

def keep_typing(chat_id, bot, stop_event):
    """Continuously show typing indicator until stop_event is set"""
    while not stop_event.is_set():
        try:
            bot.send_chat_action(chat_id=chat_id, action='typing')
            time.sleep(4)  # Telegram typing indicators last ~5 seconds
        except Exception as e:
            break

def handle_message(update: Update, context: CallbackContext) -> None:
    """Process user messages and respond using the LLM."""
    user_message = update.message.text
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = str(user.id)  # Convert to string for consistency
    
    # Log the user's message
    user_logger.info(f"User {user_id} ({user.username}): {user_message}")
    
    # Create a stop event for the typing thread
    typing_stop = threading.Event()
    
    # Start typing indicator in a separate thread
    typing_thread = threading.Thread(
        target=keep_typing,
        args=(chat_id, context.bot, typing_stop),
        daemon=True
    )
    typing_thread.start()
    
    try:
        # Process the message
        response = process_query(user_message, user_id)
        
        # Stop typing indicator
        typing_stop.set()
        typing_thread.join(timeout=1)  # Wait for thread to finish
        
        # Send response
        update.message.reply_text(response)
        
        # Log the bot's response
        user_logger.info(f"Bot to {user_id}: {response[:100]}...")
    except Exception as e:
        # Ensure typing stops if there's an error
        typing_stop.set()
        user_logger.error(f"Error processing message: {e}")
        update.message.reply_text("Sorry, I encountered an error while processing your message.")

def main():
    # Get token from environment variable
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set!")
        return
    
    memory = get_memory()
    atexit.register(memory.shutdown)
    
    global updater
    updater = Updater(token)
    dp = updater.dispatcher

    # Add handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stats", stats_command))
    dp.add_handler(CommandHandler("calendar", calendar_command))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Start the reminder scheduler
    reminder_scheduler.start(updater.bot)
    
    # Register shutdown function for the scheduler
    atexit.register(reminder_scheduler.stop)


    updater.start_polling()
    print("Bot is running!")
    user_logger.info("Bot started successfully")
    updater.idle()

if __name__ == "__main__":
    main()