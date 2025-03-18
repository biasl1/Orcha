import threading
import time
import logging
from datetime import datetime, timedelta
from utils.calendar import calendar_system
from utils.llm_reminder_generator import LLMReminderGenerator

logger = logging.getLogger(__name__)

class ReminderScheduler:
    """Schedules and sends reminders to users"""
    
    def __init__(self, bot=None):
        """Initialize the scheduler"""
        self.bot = bot  # Telegram bot instance
        self.should_run = False
        self.scheduler_thread = None
        self.check_interval = 60  # Check every 60 seconds by default
        self.reminder_generator = LLMReminderGenerator()
    
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
    
    def _check_reminders(self):
        """Check for due reminders and send notifications"""
        if not self.bot:
            return
            
        try:
            due_reminders = calendar_system.get_due_reminders()
            if due_reminders:
                logger.info(f"Found {len(due_reminders)} due reminders")
                
            for reminder in due_reminders:
                try:
                    user_id = reminder['user_id']
                    event = reminder['event']
                    
                    logger.info(f"Processing reminder for user {user_id}: {event['title']}")
                    
                    # Generate personalized reminder using LLM
                    message = self.reminder_generator.generate_reminder(user_id, event)
                        
                    # Send notification
                    try:
                        chat_id = int(user_id)
                        self.bot.send_message(
                            chat_id=chat_id,
                            text=message,
                            parse_mode="Markdown"
                        )
                        logger.info(f"Sent LLM-generated reminder to user {user_id} for event '{event['title']}'")
                    except ValueError:
                        logger.error(f"Invalid user_id format: {user_id}")
                except Exception as e:
                    logger.error(f"Error processing reminder: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error in reminder scheduler: {e}", exc_info=True)
    

    def _scheduler_loop(self):
        """Main scheduler loop that periodically checks for reminders"""
        logger.info("Reminder scheduler loop started")
        
        while self.should_run:
            try:
                self._check_reminders()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                
            # Sleep until next check
            time.sleep(self.check_interval)
        
        logger.info("Reminder scheduler loop stopped")
# Global scheduler instance
reminder_scheduler = ReminderScheduler()