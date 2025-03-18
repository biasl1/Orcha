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
import pytz

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


def reset_user_command(update: Update, context: CallbackContext) -> None:
    """Handler for /reset command - resets user data"""
    admin = update.effective_user
    
    # Only authorized admins can reset user data
    authorized_admins = [1720592375, 1473396937]  # Your admin user IDs
    if admin.id not in authorized_admins:
        update.message.reply_text("Sorry, you're not authorized to reset user data.")
        return
    
    # Check if a user ID was provided
    if not context.args or len(context.args) != 1:
        update.message.reply_text("Please provide a user ID to reset. Example: `/reset 123456789`")
        return
    
    try:
        # Get the user ID to reset
        target_user_id = str(context.args[0])
        
        # Reset conversation history
        from models.llm_handler import conversation_manager
        conv_reset = conversation_manager.reset_user_data(target_user_id)
        
        # Reset vector memory
        memory = get_memory()
        mem_reset = memory.reset_user_memory(target_user_id)
        
        # Reset calendar
        cal_reset = calendar_system.reset_user_calendar(target_user_id)
        
        # Log the reset operation
        user_logger.info(f"Admin {admin.id} reset data for user {target_user_id}")
        
        # Report success/failure
        update.message.reply_text(
            f"Reset for user {target_user_id}:\n"
            f"- Conversation history: {'✅ Reset' if conv_reset else '❌ No data found'}\n"
            f"- Long-term memory: {'✅ Reset' if mem_reset else '❌ No data found'}\n"
            f"- Calendar events: {'✅ Reset' if cal_reset else '❌ No data found'}"
        )
        
    except Exception as e:
        update.message.reply_text(f"Error resetting user data: {str(e)}")
        logger.error(f"Error in reset command: {str(e)}")
def reset_my_data_command(update: Update, context: CallbackContext) -> None:
    """Handler for /resetme command - allows users to reset their own data"""
    user = update.effective_user
    user_id = str(user.id)
    
    # Ask for confirmation
    update.message.reply_text(
        "⚠️ This will delete all your conversation history, memories, and calendar events. "
        "This action cannot be undone.\n\n"
        "To confirm, reply with `/confirmreset`"
    )
    
    # Store the pending reset in user data
    context.user_data["pending_reset"] = True

def check_reminders():
    """Check for due reminders and send notifications"""
    try:
        due_reminders = calendar_system.get_due_reminders()
        
        for reminder in due_reminders:
            user_id = reminder["user_id"]
            event = reminder["event"]
            
            try:
                bot.send_message(
                    chat_id=int(user_id),
                    text=f"🔔 REMINDER: {event['title']}",
                    parse_mode="Markdown"
                )
                user_logger.info(f"Sent reminder to user {user_id}: {event['title']}")
            except Exception as e:
                logger.error(f"Error sending reminder to {user_id}: {e}")
    except Exception as e:
        logger.error(f"Error checking reminders: {e}")

def confirm_reset_command(update: Update, context: CallbackContext) -> None:
    """Handler for /confirmreset command - confirms user data reset"""
    user = update.effective_user
    user_id = str(user.id)
    
    # Check if reset was requested
    if not context.user_data.get("pending_reset"):
        update.message.reply_text("No reset was requested. Use `/resetme` first.")
        return
    
    # Clear the pending flag
    context.user_data["pending_reset"] = False
    
    try:
        # Reset all user data
        from models.llm_handler import conversation_manager
        conversation_manager.reset_user_data(user_id)
        
        memory = get_memory()
        memory.reset_user_memory(user_id)
        
        calendar_system.reset_user_calendar(user_id)
        
        # Log the self-reset
        user_logger.info(f"User {user_id} reset their own data")
        
        update.message.reply_text(
            "✅ Your data has been reset. I've forgotten our previous conversations, "
            "any stored memories, and your calendar events."
        )
        
    except Exception as e:
        update.message.reply_text(f"Error resetting your data: {str(e)}")

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
    dp.add_handler(CommandHandler("reset", reset_user_command))
    dp.add_handler(CommandHandler("resetme", reset_my_data_command))
    dp.add_handler(CommandHandler("confirmreset", confirm_reset_command))
    # Start the reminder scheduler
    reminder_scheduler.start(updater.bot)
    
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(timezone=pytz.UTC)
    scheduler.add_job(check_reminders, 'interval', seconds=30)
    scheduler.start()

    # Make sure to register a clean shutdown
    atexit.register(lambda: scheduler.shutdown())

    updater.start_polling()
    print("Bot is running!")
    user_logger.info("Bot started successfully")
    updater.idle()

if __name__ == "__main__":
    main()