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
    def get_calendar_context(self, user_id, days_ahead=7):
        """Generate rich calendar context for LLM reasoning"""
        user_id = str(user_id)
        now = datetime.now()
        
        # Get events
        upcoming = self.get_upcoming_events(user_id, days=days_ahead)
        if not upcoming:
            return "You have no scheduled events for the next week."

        # Organize by timeframe
        today = []
        tomorrow = []
        this_week = []
        next_week = []
        
        for event in upcoming:
            event_time = event['timestamp']
            event_day = event_time.date()
            
            if event_day == now.date():
                today.append(event)
            elif event_day == (now + timedelta(days=1)).date():
                tomorrow.append(event)
            elif event_time < now + timedelta(days=7):
                this_week.append(event)
            else:
                next_week.append(event)
        
        # Build context
        context_parts = []
        
        # Today's events
        if today:
            today_str = "Today's schedule:\n"
            for event in today:
                time_str = event['timestamp'].strftime("%I:%M %p")
                today_str += f"- {time_str}: {event['title']}"
                if event.get('description'):
                    today_str += f" ({event['description']})"
                today_str += "\n"
            context_parts.append(today_str)
        
        # Tomorrow's events
        if tomorrow:
            tomorrow_str = "Tomorrow's schedule:\n"
            for event in tomorrow:
                time_str = event['timestamp'].strftime("%I:%M %p")
                tomorrow_str += f"- {time_str}: {event['title']}\n"
            context_parts.append(tomorrow_str)
        
        # This week's events
        if this_week:
            week_str = "Later this week:\n"
            for event in this_week:
                day_time = event['timestamp'].strftime("%A at %I:%M %p")
                week_str += f"- {day_time}: {event['title']}\n"
            context_parts.append(week_str)
        
        # Next week's events
        if next_week:
            next_week_str = "Next week:\n"
            for event in next_week:
                day_time = event['timestamp'].strftime("%A, %b %d at %I:%M %p")
                next_week_str += f"- {day_time}: {event['title']}\n"
            context_parts.append(next_week_str)
        
        # Add schedule analysis
        context_parts.append(self._analyze_schedule(user_id))
        
        return "\n".join(context_parts)

    def _analyze_schedule(self, user_id):
        """Analyze user's schedule for patterns"""
        # Get user's past events (last 30 days)
        now = datetime.now()
        past_cutoff = now - timedelta(days=30)
        
        user_events = self.get_all_user_events(user_id)
        past_events = [e for e in user_events if past_cutoff <= e['timestamp'] <= now]
        
        if not past_events:
            return ""
        
        # Basic analysis
        weekday_counts = [0] * 7  # Monday to Sunday
        hour_counts = [0] * 24    # 0-23 hours
        
        for event in past_events:
            weekday_counts[event['timestamp'].weekday()] += 1
            hour_counts[event['timestamp'].hour] += 1
        
        # Find most common day and time
        busiest_day_idx = weekday_counts.index(max(weekday_counts))
        busiest_hour = hour_counts.index(max(hour_counts))
        
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        busiest_day = days[busiest_day_idx]
        
        # Format time
        busiest_time = f"{busiest_hour}:00"
        if busiest_hour == 0:
            busiest_time = "midnight"
        elif busiest_hour == 12:
            busiest_time = "noon"
        elif busiest_hour > 12:
            busiest_time = f"{busiest_hour-12}:00 PM"
        else:
            busiest_time = f"{busiest_hour}:00 AM"
        
        return f"Based on your history, you tend to schedule most activities on {busiest_day}s around {busiest_time}."

    def get_all_user_events(self, user_id):
        """Get all events for a user (including past ones)"""
        user_id = str(user_id)
        if user_id not in self.user_calendars:
            return []
        
        # Return a copy to avoid modifying original data
        return self.user_calendars[user_id].copy()
    
    def _handle_calendar_creation(query: str, user_id: str) -> str:
        """Extract event details from natural language and create calendar event"""
        try:
            # First, extract datetime
            event_time = DateTimeExtractor.extract_datetime(query)
            
            if not event_time:
                # If no time found, ask LLM to help understand the request
                system_prompt = """You are a calendar assistant. Extract the following from the text:
    1. Event title
    2. Date and time (if specified)
    3. Duration (if specified)
    4. Any other relevant details

    Format your response as JSON:
    {
    "title": "extracted title",
    "date": "extracted date or null",
    "time": "extracted time or null",
    "duration": "extracted duration or null",
    "details": "other details"
    }"""

                # Use a separate LLM call to analyze the scheduling request
                extraction_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract scheduling information from: {query}"}
                ]
                
                extraction_response = llm_client.query(extraction_messages, temperature=0.2)
                response_text = extraction_response["message"]["content"]
                
                # Try to extract JSON from response
                try:
                    # Find JSON block (might be formatted in markdown)
                    import re
                    json_match = re.search(r'```(?:json)?(.*?)```', response_text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                    else:
                        json_str = response_text
                    
                    # Clean and parse JSON
                    json_str = json_str.strip()
                    extracted = json.loads(json_str)
                    
                    title = extracted.get("title", "Untitled Event")
                    
                    # Try to construct a datetime from parts
                    if extracted.get("date") or extracted.get("time"):
                        # Use simple heuristics - this could be improved with a more sophisticated parser
                        date_str = extracted.get("date", "today")
                        time_str = extracted.get("time", "12:00")
                        
                        datetime_str = f"{date_str} at {time_str}"
                        event_time = DateTimeExtractor.extract_datetime(datetime_str)
                    
                    description = extracted.get("details", "")
                    
                except Exception as e:
                    logger.error(f"Error parsing extraction response: {e}")
                    return "I couldn't understand the event details. Could you please specify when this event should be scheduled?"
                    
            # If we found a time, extract the title
            if event_time:
                # Extract title using simple heuristics
                title = query
                
                # Remove time indicators
                time_indicators = ["today", "tomorrow", "next", "on", "at", "schedule", "create event"]
                for indicator in time_indicators:
                    title = title.replace(indicator, "")
                    
                # Clean up title
                title = title.strip()
                if not title or len(title) < 3:
                    title = "Untitled Event"
                
                # Add the event
                event = calendar_system.add_event(
                    user_id=user_id,
                    title=title,
                    timestamp=event_time,
                    description="",
                    reminder=True
                )
                
                # Format response
                day_str = event_time.strftime("%A, %B %d")
                time_str = event_time.strftime("%I:%M %p")
                return f"✅ I've added \"{title}\" to your calendar on {day_str} at {time_str}."
            
            return "I couldn't determine when to schedule this event. Could you please specify a date and time?"
            
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return "I had trouble creating that calendar event. Could you try again with a clearer date and time?"

# Global calendar instance
calendar_system = CalendarSystem()