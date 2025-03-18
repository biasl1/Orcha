import threading
import time
import logging
from datetime import datetime, timedelta
from utils.calendar import calendar_system

logger = logging.getLogger(__name__)

class ReminderScheduler:
    """Schedules and sends reminders to users"""
    
    def __init__(self, bot=None):
        """Initialize the scheduler"""
        self.bot = bot  # Telegram bot instance
        self.should_run = False
        self.scheduler_thread = None
        self.check_interval = 60  # Check every 60 seconds by default
    
    def start(self, bot=None):
        """Start the reminder scheduler"""
        if bot:
            self.bot = bot
            
        if self.bot is None:
            logger.error("Cannot start reminder scheduler without a bot instance")
            return False
            
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            logger.warning("Reminder scheduler already running")
            return False
        
        self.should_run = True
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop, 
            name="ReminderScheduler",
            daemon=True
        )
        self.scheduler_thread.start()
        logger.info("Reminder scheduler started")
        return True
    
    def stop(self):
        """Stop the reminder scheduler"""
        self.should_run = False
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        logger.info("Reminder scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop that checks for due reminders"""
        while self.should_run:
            try:
                self._check_reminders()
            except Exception as e:
                logger.error(f"Error in reminder scheduler: {e}")
                
            # Sleep until next check
            time.sleep(self.check_interval)
    
    def _check_reminders(self):
        """Check for due reminders and send notifications"""
        if not self.bot:
            return
            
        due_reminders = calendar_system.get_due_reminders()
        for reminder in due_reminders:
            try:
                user_id = reminder['user_id']
                event = reminder['event']
                
                # Format message
                message = f"🔔 *Reminder*: {event['title']}"
                if event.get('description'):
                    message += f"\n\n{event['description']}"
                    
                # Send notification - ensure user_id is numeric
                try:
                    chat_id = int(user_id)
                    self.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode="Markdown"
                    )
                    logger.info(f"Sent reminder to user {user_id} for event '{event['title']}'")
                except ValueError:
                    logger.error(f"Invalid user_id format: {user_id}")
            except Exception as e:
                logger.error(f"Error sending reminder: {e}", exc_info=True)

# Global scheduler instance
reminder_scheduler = ReminderScheduler()