import requests
import json
import subprocess
import time
import logging
import uuid
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from models.memory_handler import get_memory
from datetime import datetime, timedelta
from utils.calendar import calendar_system
from utils.processing import DateTimeExtractor


# Set up logging
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Lenny, a professional AI assistant.

Time information provided with each query:
- FIRST_CONVERSATION: Welcome the user
- SAME_DAY: Be conversational but acknowledge you've spoken earlier today
- RETURNING_USER: Greet user as returning

Be professional, helpful, and focused in your responses.
"""

class LLMException(Exception):
    """Custom exception for LLM-related errors"""
    pass

class ResponseValidator:
    """Validates and improves LLM responses"""
    
    @staticmethod
    def validate(response: str) -> bool:
        """Check if a response meets quality criteria"""
        if not response or len(response) < 10:
            return False
        return True
    
    @staticmethod
    def clean(response: str) -> str:
        """Clean up response text"""
        # Remove redundant prefixes often added by LLMs
        prefixes = ["Assistant:", "Bot:", "AI:"]
        for prefix in prefixes:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        return response

class ConversationManager:
    """Manages conversation context and history with time awareness"""
    
    def __init__(self, max_conversation_turns: int = 5):
        self.conversations: Dict[str, List[Dict[str, Any]]] = {}
        self.max_turns = max_conversation_turns
    
    def add_exchange(self, user_id: str, query: str, response: str) -> None:
        """Add a query-response pair to conversation history"""
        now = datetime.now()
        
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        
        # Simply add the messages with their timestamps
        self.conversations[user_id].append({
            "role": "user",
            "content": query,
            "timestamp": now.isoformat()
        })
        
        self.conversations[user_id].append({
            "role": "assistant",
            "content": response,
            "timestamp": now.isoformat()
        })
        
        # Trim to max_turns
        if len(self.conversations[user_id]) > self.max_turns * 2:
            self.conversations[user_id] = self.conversations[user_id][-self.max_turns * 2:]
    
    def reset_user_data(self, user_id: str) -> bool:
        """Reset conversation history for a specific user"""
        user_id = str(user_id)
        try:
            if user_id in self.conversations:
                del self.conversations[user_id]
                logger.info(f"Reset conversation history for user {user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error resetting conversation for user {user_id}: {e}")
            return False
    def get_conversation(self, user_id: str) -> List[Dict[str, str]]:
        """Get formatted conversation history for the LLM"""
        if user_id not in self.conversations:
            return []
        
        # Convert internal conversation format to LLM format
        formatted = []
        for msg in self.conversations[user_id]:
            formatted.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        return formatted

# Initialize conversation manager
conversation_manager = ConversationManager()

class LLMClient:
    """Client for interacting with LLM services"""
    
    def __init__(self, host: str = "localhost", timeout: int = 3000):
        self.host = host
        self.timeout = timeout
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "average_latency": 0
        }
    
    def check_availability(self) -> bool:
        """Check if LLM service is available"""
        try:
            response = requests.get(
                f"http://{self.host}:11434/api/version",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def query(self, 
              messages: List[Dict[str, str]], 
              model: str = "llama2",
              temperature: float = 0.7,
              max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Send a query to the LLM and return the response"""
        start_time = time.time()
        self.metrics["total_requests"] += 1
        
        try:
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "temperature": temperature
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
            
            response = requests.post(
                f"http://{self.host}:11434/api/chat",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                self.metrics["failed_requests"] += 1
                raise LLMException(f"LLM request failed with status {response.status_code}: {response.text[:200]}")
            
            response_data = response.json()
            if "message" not in response_data or "content" not in response_data["message"]:
                self.metrics["failed_requests"] += 1
                raise LLMException(f"Unexpected response format: {response_data}")
            
            # Update metrics
            self.metrics["successful_requests"] += 1
            latency = time.time() - start_time
            self.metrics["average_latency"] = (
                (self.metrics["average_latency"] * (self.metrics["successful_requests"] - 1) + latency) / 
                self.metrics["successful_requests"]
            )
            
            return response_data
            
        except json.JSONDecodeError as e:
            self.metrics["failed_requests"] += 1
            raise LLMException(f"Failed to parse JSON response: {str(e)}")
        except requests.exceptions.Timeout:
            self.metrics["failed_requests"] += 1
            raise LLMException("LLM request timed out")
        except Exception as e:
            self.metrics["failed_requests"] += 1
            raise LLMException(f"Error querying LLM: {str(e)}")

# Initialize LLM client
llm_client = LLMClient()

# Replace _get_calendar_context with this enhanced version
def _get_calendar_context(user_id: str) -> str:
    """Get comprehensive calendar context for the LLM"""
    try:
        # Get rich calendar context using the new method
        context = calendar_system.get_calendar_context(user_id)
        if context:
            return f"\n\n---\nCALENDAR INFORMATION:\n{context}\n---\n"
        return ""
    except Exception as e:
        logger.error(f"Error getting calendar context: {str(e)}")
        return ""

# Add this helper function for natural language calendar operations
def _detect_calendar_intent(query: str) -> tuple:
    """Detect basic calendar intents in user query"""
    query_lower = query.lower()
    
    # Map keywords to intents
    intent_patterns = {
        "create": ["schedule", "add event", "create event", "new appointment"],
        "view": ["what's on my calendar", "my schedule", "what do i have", "appointments"],
        "delete": ["cancel", "delete event", "remove appointment"],
        "remind": ["remind me", "reminder", "remember to"],
        "find_time": ["free time", "available", "when am i free"]
    }
    
    # Check for intent matches
    for intent, patterns in intent_patterns.items():
        if any(pattern in query_lower for pattern in patterns):
            return intent, query
    
    return None, query

def get_simple_time_context(user_id):
    """Generate simple time context that's hard to misinterpret"""
    now = datetime.now()
    today = now.strftime("%A, %B %d, %Y")
    
    # No previous conversation case
    if user_id not in conversation_manager.conversations or not conversation_manager.conversations[user_id]:
        return f"FIRST_CONVERSATION | TODAY: {today}"
    
    # Find last user timestamp
    last_time = None
    for msg in reversed(conversation_manager.conversations[user_id]):
        if msg["role"] == "user" and "timestamp" in msg:
            try:
                last_time = datetime.fromisoformat(msg["timestamp"])
                break
            except:
                pass
    
    if not last_time:
        return f"FIRST_CONVERSATION | TODAY: {today}"
    
    # Simple binary context
    if last_time.date() == now.date():
        return f"SAME_DAY | TODAY: {today}"
    else:
        last_date = last_time.strftime("%A, %B %d, %Y")
        return f"RETURNING_USER | LAST_TALKED: {last_date} | TODAY: {today}"

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
            from utils.calendar import calendar_system
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
    

def process_query(query: str, user_id: Optional[str] = None) -> str:
    """Process a user query with context and return a response"""
    request_id = str(uuid.uuid4())[:8]
    current_time = datetime.now()
    logger.info(f"[{request_id}] Processing query: {query[:50]}...")
    
    try:
        # Calendar intent detection
        calendar_intent, _ = _detect_calendar_intent(query)
        
        # Special handlers for calendar operations
        if calendar_intent in ["remind", "create"]:
            handler = _handle_reminder if calendar_intent == "remind" else _handle_calendar_creation
            result = handler(query, user_id)
            
            # Store in history/memory
            if user_id:
                conversation_manager.add_exchange(user_id, query, result)
                try:
                    memory = get_memory()
                    memory.add_interaction(user_id, query, result, priority=True)
                except Exception as e:
                    logger.warning(f"Memory storage error: {str(e)}")
            return result
            
        # Prepare context
        time_context = get_simple_time_context(user_id) if user_id else "FIRST_CONVERSATION"
        messages = [{"role": "system", "content": f"{time_context}\n\n{SYSTEM_PROMPT}"}]
        
        # Add calendar context if appropriate
        is_calendar_query = calendar_intent in ["view", "find_time", "delete"]
        if user_id:
            if is_calendar_query:
                calendar_context = _get_calendar_context(user_id)
                if calendar_context:
                    messages[0]["content"] += calendar_context
            else:
                # Just add brief calendar info for non-calendar queries
                events_today = calendar_system.get_upcoming_events(user_id, days=1)
                if events_today:
                    messages[0]["content"] += f"\n\nYou have {len(events_today)} event(s) today."
        
        # Add conversation history and memory
        if user_id:
            messages.extend(conversation_manager.get_conversation(user_id))
            memory = get_memory()
            query = memory.get_relevant_context(user_id, query)
            
        # Add current query
        messages.append({"role": "user", "content": query})
        
        # Generate response
        if not llm_client.check_availability():
            return "Sorry, I'm temporarily unavailable. Please try again in a moment."
            
        response_data = llm_client.query(messages)
        response_text = ResponseValidator.clean(response_data["message"]["content"])
        
        # Save to history/memory
        if user_id:
            conversation_manager.add_exchange(user_id, query, response_text)
            try:
                memory = get_memory()
                memory.add_interaction(user_id, query, response_text)
            except Exception as e:
                logger.warning(f"Memory storage error: {str(e)}")
                
        return response_text
    
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        return "I'm sorry, but I encountered an error. Please try again."

def _handle_reminder(query: str, user_id: str) -> str:
    """Extract reminder details and create a reminder event"""
    from utils.processing import DateTimeExtractor
    from utils.calendar import calendar_system
    from datetime import datetime, timedelta
    import re
    
    try:
        # First try to extract time from query
        reminder_time = DateTimeExtractor.extract_datetime(query)
        
        # If no specific time found, look for relative time indicators
        if not reminder_time:
            # Look for patterns like "in 10 minutes" or "after 2 hours"
            time_pattern = r'in (\d+) (minute|minutes|mins|min|hour|hours|hr|hrs)'
            match = re.search(time_pattern, query.lower())
            
            if match:
                amount = int(match.group(1))
                unit = match.group(2)
                
                now = datetime.now()
                
                if unit.startswith('minute') or unit.startswith('min'):
                    reminder_time = now + timedelta(minutes=amount)
                elif unit.startswith('hour') or unit.startswith('hr'):
                    reminder_time = now + timedelta(hours=amount)
        
        # If we found a time, create the reminder
        if reminder_time:
            # Extract what the reminder is for
            action_text = query
            
            # Try to extract the action (what to be reminded of)
            action_patterns = [
                r'remind me to (.+?) in \d+',
                r'remind me in \d+.+? to (.+)',
                r'remind me (.+?) after \d+',
                r'remember me in \d+.+? to (.+)',
                r'reminder to (.+?) in \d+',
                r'reminder for (.+?) in \d+',
            ]
            
            for pattern in action_patterns:
                match = re.search(pattern, query.lower())
                if match:
                    action_text = match.group(1).strip()
                    break
            
            # Clean up the title if needed
            if len(action_text) > 100 or action_text.lower() == query.lower():
                # Just extract relevant part or use generic title
                action_text = "Reminder"
            
            # Create calendar event
            event = calendar_system.add_event(
                user_id=user_id,
                title=action_text,
                timestamp=reminder_time,
                description="Created from chat reminder",
                reminder=True
            )
            
            # Format time for response
            if (reminder_time - datetime.now()).total_seconds() < 3600:  # Less than an hour
                minutes = round((reminder_time - datetime.now()).total_seconds() / 60)
                time_str = f"{minutes} minute{'s' if minutes != 1 else ''}"
            else:
                time_str = reminder_time.strftime("%I:%M %p")
            
            return f"✅ I'll remind you to {action_text} in {time_str}."
        
        return "I couldn't determine when to set your reminder. Could you please specify a time? For example, 'Remind me in 10 minutes' or 'Remind me at 3pm'."
        
    except Exception as e:
        logger.error(f"Error setting reminder: {e}")
        return "I had trouble setting that reminder. Could you try again with a clearer time?"

def get_metrics() -> Dict[str, Any]:
    """Return current performance metrics"""
    return {
        "llm": llm_client.metrics,
        "conversations": len(conversation_manager.conversations),
        "timestamp": datetime.now().isoformat()
    }