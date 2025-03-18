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

# System prompt template to guide behavior
SYSTEM_PROMPT = """You are LennyBot, a professional AI assistant with time awareness. Your responses should:

1. Be helpful, accurate, and professional
2. Acknowledge time context - note how recently or long ago previous interactions occurred
3. Consider the current time of day and date in your responses
4. Reference specific dates and times when discussing schedules or deadlines
5. Note significant gaps between conversations (e.g., "It's been -- since we last talked")
6. Maintain professionalism while being mindful of time-appropriate greetings (morning/evening)
7. Intelligently reason about calendar information when it's provided
8. Offer relevant suggestions based on the user's schedule
9. Identify potential schedule conflicts when they arise

The current date and time is provided with each query. Calendar information is included when available. Use this information to make your responses temporally relevant and helpful for schedule management.
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
        """Add a query-response exchange to user's conversation history"""
        now = datetime.now()
        
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        
        # Calculate time since last message if available
        time_context = ""
        if self.conversations[user_id]:
            last_msg_time = datetime.fromisoformat(self.conversations[user_id][-1]["timestamp"])
            delta = now - last_msg_time
            
            if delta.days > 0:
                time_context = f" (after {delta.days} days)"
            elif delta.seconds > 3600:
                time_context = f" (after {delta.seconds // 3600} hours)"
            elif delta.seconds > 60:
                time_context = f" (after {delta.seconds // 60} minutes)"
        
        # Add user message with timestamp
        self.conversations[user_id].append({
            "role": "user",
            "content": query,
            "timestamp": now.isoformat(),
            "time_context": time_context
        })
        
        # Add assistant response with timestamp
        self.conversations[user_id].append({
            "role": "assistant",
            "content": response,
            "timestamp": now.isoformat(),
            "time_context": ""  # No delay for assistant response
        })
        
        # Keep only recent turns
        if len(self.conversations[user_id]) > self.max_turns * 2:
            self.conversations[user_id] = self.conversations[user_id][-self.max_turns * 2:]
    
    def get_recent_conversation(self, user_id: str) -> List[Dict[str, str]]:
        """Get recent conversation history for a user with time information"""
        if user_id not in self.conversations:
            return []
        
        # Convert to the format expected by LLM, including time context
        formatted_messages = []
        
        for msg in self.conversations[user_id]:
            # Format message with time context if available
            content = msg["content"]
            if msg.get("time_context"):
                content = f"{content} {msg['time_context']}"
                
            formatted_messages.append({
                "role": msg["role"],
                "content": content
            })
        
        return formatted_messages

# Initialize conversation manager
conversation_manager = ConversationManager()

class LLMClient:
    """Client for interacting with LLM services"""
    
    def __init__(self, host: str = "localhost", timeout: int = 300):
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

def check_docker_ollama() -> bool:
    """Check if Ollama container is running, start if needed."""
    try:
        # Check if container exists and is running
        result = subprocess.run(
            ["docker", "inspect", "ollama"], 
            capture_output=True, 
            text=True
        )
        
        if result.returncode != 0:
            logger.warning("Ollama container not found")
            return False
            
        container_info = json.loads(result.stdout)[0]
        is_running = container_info.get("State", {}).get("Running", False)
        
        if not is_running:
            logger.info("Starting Ollama container...")
            subprocess.run(["docker", "start", "ollama"], check=True)
            time.sleep(3)
        
        return True
    except Exception as e:
        logger.error(f"Error checking Docker: {e}")
        return False

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
    """Detect various calendar-related intents in user query"""
    query_lower = query.lower()
    
    # Common calendar operations
    if any(x in query_lower for x in ["schedule", "add event", "create event", "new appointment"]):
        return "create", query
        
    if any(x in query_lower for x in ["what's on my calendar", "my schedule", "what do i have", "appointments", "upcoming events"]):
        return "view", query
        
    if any(x in query_lower for x in ["cancel", "delete event", "remove appointment"]):
        return "delete", query
        
    if "remind" in query_lower or "reminder" in query_lower:
        return "remind", query
        
    if any(x in query_lower for x in ["free time", "available", "when am i free", "find time"]):
        return "find_time", query
        
    # No calendar intent detected
    return None, query

# Update the process_query function to handle calendar requests
def process_query(query: str, user_id: Optional[str] = None) -> str:
    """Process a user query with context and return a response"""
    request_id = str(uuid.uuid4())[:8]
    current_time = datetime.now()
    logger.info(f"[{request_id}] Processing query for user {user_id} at {current_time.isoformat()}: {query[:50]}...")

    # Initialize is_calendar_query to False by default
    is_calendar_query = False

    try:
        # Detect calendar-related intents
        calendar_intent, _ = _detect_calendar_intent(query)
        
        # Handle calendar-specific intents
        if calendar_intent == "remind":
            result = _handle_reminder(query, user_id)
            # Store in memory and conversation
            if user_id:
                conversation_manager.add_exchange(user_id, query, result)
                try:
                    memory = get_memory()
                    memory.add_interaction(user_id, query, result, priority=True)
                except Exception as e:
                    logger.warning(f"Error storing in memory: {str(e)}")
            return result
        elif calendar_intent == "create":
            result = _handle_calendar_creation(query, user_id)
            if user_id:
                conversation_manager.add_exchange(user_id, query, result)
                try:
                    memory = get_memory()
                    memory.add_interaction(user_id, query, result, priority=True)
                except Exception as e:
                    logger.warning(f"Error storing in memory: {str(e)}")
            return result
        elif calendar_intent == "view":
            # For viewing calendar, we'll use the calendar context in the LLM response
            is_calendar_query = True
        elif calendar_intent == "find_time":
            # For find_time, add available slots to the context
            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)
            slots_today = calendar_system.suggest_times(user_id, preferred_date=today)
            slots_tomorrow = calendar_system.suggest_times(user_id, preferred_date=tomorrow)
            
            available_text = "Available times:\n\nToday:\n"
            for start, end in slots_today:
                available_text += f"- {start.strftime('%I:%M %p')} to {end.strftime('%I:%M %p')}\n"
            
            available_text += "\nTomorrow:\n"
            for start, end in slots_tomorrow:
                available_text += f"- {start.strftime('%I:%M %p')} to {end.strftime('%I:%M %p')}\n"
            
            # Add this to the system prompt
            system_prompt += f"\n\n{available_text}"
            is_calendar_query = True

        # Prepare messages
        messages = []
        
        # Add system prompt with current time
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        system_prompt = f"{SYSTEM_PROMPT}\n\nCurrent date and time: {current_time_str}"
        
        # Always include calendar context for calendar-related queries
        if user_id and is_calendar_query:
            calendar_context = _get_calendar_context(user_id)
            if (calendar_context):
                system_prompt += calendar_context
                
                # For calendar-specific operations, add special instructions
                if calendar_intent == "create":
                    system_prompt += "\nThe user wants to create a calendar event. Help extract the event title, date, time, and any other details."
                elif calendar_intent == "view":
                    system_prompt += "\nThe user wants to view their calendar. Summarize their schedule in a helpful way."
                elif calendar_intent == "delete":
                    system_prompt += "\nThe user wants to cancel or delete an event. Help identify which event they're referring to."
                elif calendar_intent == "find_time":
                    system_prompt += "\nThe user wants to find available time. Analyze their schedule and suggest some free slots."
        
        # Regular (non-calendar) queries can still benefit from calendar context sometimes
        elif user_id:
            events_today = calendar_system.get_upcoming_events(user_id, days=1)
            if events_today:
                # Only add brief calendar context for regular queries
                calendar_brief = f"You have {len(events_today)} event(s) scheduled today."
                system_prompt += f"\n\n{calendar_brief}"
        
        messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation context if user_id available
        if user_id:
            recent_conversation = conversation_manager.get_recent_conversation(user_id)
            if recent_conversation:
                messages.extend(recent_conversation)
        
        # Get memory instance and retrieve relevant context
        memory = get_memory()
        context = None
        if user_id:
            try:
                context = memory.get_relevant_context(user_id, query)
                # Only include context if it's different from the original query
                if context and context != query:
                    messages.append({
                        "role": "system", 
                        "content": f"Relevant from previous conversations: {context}"
                    })
            except Exception as e:
                logger.warning(f"[{request_id}] Error retrieving memory context: {str(e)}")
        
        query_with_time = f"{query}\n\nCurrent time: {current_time_str}"
        # Add current query if not already in conversation
        if not messages or messages[-1]["role"] != "user" or messages[-1]["content"] != query:
            messages.append({"role": "user", "content": query_with_time})
        
        # Check LLM availability
        if not llm_client.check_availability():
            logger.error(f"[{request_id}] LLM service unavailable")
            return "I'm sorry, but I'm currently unable to process your request due to a service issue. Please try again in a few moments."
        
        # Query LLM
        logger.debug(f"[{request_id}] Sending messages to LLM: {len(messages)} messages")
        response_data = llm_client.query(messages)
        
        # Extract and validate response
        response_text = response_data["message"]["content"]
        response_text = ResponseValidator.clean(response_text)
        
        # Add to conversation history
        if user_id:
            conversation_manager.add_exchange(user_id, query, response_text)
            
            # Store in vector memory
            try:
                memory.add_interaction(user_id, query, response_text)
            except Exception as e:
                logger.warning(f"[{request_id}] Error storing in memory: {str(e)}")
        
        logger.info(f"[{request_id}] Successfully processed query")
        return response_text
        
    except LLMException as e:
        logger.error(f"[{request_id}] LLM error: {str(e)}")
        return "I encountered a problem while processing your request. Let me try again or please rephrase your question."
        
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error: {str(e)}", exc_info=True)
        return "I'm sorry, but something went wrong on my end. Please try again in a moment."

def _is_reminder_request(query: str) -> bool:
    """Check if query is a reminder request"""
    reminder_keywords = [
        "remind me", "set a reminder", "remember", "don't forget", 
        "schedule", "calendar", "appointment"
    ]
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in reminder_keywords)

def _handle_reminder(query: str, user_id: str) -> str:
    """Extract reminder information and save to calendar"""
    try:
        # Extract date/time
        reminder_time = DateTimeExtractor.extract_datetime(query)
        
        if not reminder_time:
            return "I'd be happy to set a reminder, but I couldn't determine when. Please specify a date or time, like 'tomorrow at 3pm' or 'next Monday'."
        
        # Extract title - simple approach: use text before "remind me" or after "to"
        title = ""
        if "remind me to" in query.lower():
            title = query.lower().split("remind me to", 1)[1].strip()
        elif "reminder to" in query.lower():
            title = query.lower().split("reminder to", 1)[1].strip()
        elif "remember to" in query.lower():
            title = query.lower().split("remember to", 1)[1].strip()
        else:
            # Fallback: use the whole query as title
            title = query
            
        # Clean up title
        time_markers = ["today", "tomorrow", "next week", "in", "at", "on"]
        for marker in time_markers:
            if f" {marker} " in title:
                title = title.split(f" {marker} ")[0].strip()
                
        if not title:
            title = "Reminder"
        
        # Add to calendar
        event = calendar_system.add_event(
            user_id=user_id,
            title=title,
            timestamp=reminder_time,
            description="",
            reminder=True
        )
        
        # Format response
        when = reminder_time.strftime("%A, %B %d at %I:%M %p")
        return f"✅ I've set a reminder for you: \"{title}\" on {when}. I'll remind you when it's time!"
        
    except Exception as e:
        logger.error(f"Error setting reminder: {e}")
        return "I'm sorry, I couldn't set that reminder. Please try again with a clearer time specification."

def get_metrics() -> Dict[str, Any]:
    """Return current performance metrics"""
    return {
        "llm": llm_client.metrics,
        "conversations": len(conversation_manager.conversations),
        "timestamp": datetime.now().isoformat()
    }