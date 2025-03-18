import json
import os
from datetime import datetime, timedelta
import pytz
import uuid
import logging

logger = logging.getLogger(__name__)

class CalendarSystem:
    """Manages user events and reminders"""
    
    def __init__(self, storage_path="./data/calendar"):
        """Initialize calendar system with storage path"""
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        self.user_calendars = {}
        self._load_all_calendars()
    
    def _get_user_file(self, user_id):
        """Get path to a user's calendar file"""
        return os.path.join(self.storage_path, f"{user_id}_calendar.json")
    
    def _load_all_calendars(self):
        """Load calendars for all users from storage"""
        if not os.path.exists(self.storage_path):
            return
            
        for filename in os.listdir(self.storage_path):
            if filename.endswith('_calendar.json'):
                user_id = filename.split('_')[0]
                self._load_user_calendar(user_id)
    
    def _load_user_calendar(self, user_id):
        """Load calendar for a specific user"""
        file_path = self._get_user_file(user_id)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    
                # Convert string dates back to datetime objects
                for event in data:
                    if 'timestamp' in event:
                        event['timestamp'] = datetime.fromisoformat(event['timestamp'])
                        
                self.user_calendars[user_id] = data
                return data
            except Exception as e:
                logger.error(f"Error loading calendar for user {user_id}: {e}")
                return []
        return []
    
    def _save_user_calendar(self, user_id):
        """Save calendar for a specific user"""
        if user_id not in self.user_calendars:
            return
            
        file_path = self._get_user_file(user_id)
        try:
            # Convert datetime objects to strings for serialization
            data = []
            for event in self.user_calendars[user_id]:
                event_copy = event.copy()
                # Convert all datetime objects to strings
                for key, value in event_copy.items():
                    if isinstance(value, datetime):
                        event_copy[key] = value.isoformat()
                data.append(event_copy)
                
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving calendar for user {user_id}: {e}")
            
    def add_event(self, user_id, title, timestamp, description="", reminder=True):
        """Add an event to a user's calendar"""
        user_id = str(user_id)  # Ensure user_id is string
        
        if user_id not in self.user_calendars:
            self.user_calendars[user_id] = []
        
        # Create the event
        event = {
            "id": str(uuid.uuid4()),
            "title": title,
            "description": description,
            "timestamp": timestamp,
            "created_at": datetime.now(),
            "reminder": reminder
        }
        
        # Add event to calendar
        self.user_calendars[user_id].append(event)
        
        # Save changes
        self._save_user_calendar(user_id)
        
        return event
    
    def get_upcoming_events(self, user_id, days=7):
        """Get all upcoming events for a user within specified days"""
        user_id = str(user_id)
        now = datetime.now()
        future = now + timedelta(days=days)
        
        if user_id not in self.user_calendars:
            return []
        
        upcoming = []
        for event in self.user_calendars[user_id]:
            event_time = event['timestamp']
            if now <= event_time <= future:
                upcoming.append(event)
        
        # Sort by timestamp
        upcoming.sort(key=lambda x: x['timestamp'])
        return upcoming
    
    def get_due_reminders(self):
        """Get all reminders that are due now across all users"""
        now = datetime.now()
        due_reminders = []
        
        for user_id, events in self.user_calendars.items():
            for event in events:
                if not event.get('reminder', False):
                    continue
                    
                # Check if reminder is due (within last minute)
                event_time = event['timestamp']
                if event_time <= now and event_time >= now - timedelta(minutes=1):
                    if not event.get('reminded', False):
                        due_reminders.append({
                            "user_id": user_id,
                            "event": event
                        })
        
        # Mark these events as reminded
        for item in due_reminders:
            user_id = item['user_id']
            event_id = item['event']['id']
            
            for event in self.user_calendars[user_id]:
                if event['id'] == event_id:
                    event['reminded'] = True
            
            self._save_user_calendar(user_id)
            
        return due_reminders
    
    def remove_event(self, user_id, event_id):
        """Remove an event from a user's calendar"""
        user_id = str(user_id)
        if user_id not in self.user_calendars:
            return False
        
        initial_count = len(self.user_calendars[user_id])
        self.user_calendars[user_id] = [e for e in self.user_calendars[user_id] if e['id'] != event_id]
        
        # If we removed something, save changes
        if len(self.user_calendars[user_id]) < initial_count:
            self._save_user_calendar(user_id)
            return True
            
        return False
    
    def clear_old_events(self, days=30):
        """Clear events older than specified days"""
        cutoff = datetime.now() - timedelta(days=days)
        
        for user_id in self.user_calendars:
            initial_count = len(self.user_calendars[user_id])
            self.user_calendars[user_id] = [
                e for e in self.user_calendars[user_id] 
                if e['timestamp'] >= cutoff
            ]
            
            if len(self.user_calendars[user_id]) < initial_count:
                self._save_user_calendar(user_id)

# Global calendar instance
calendar_system = CalendarSystem()