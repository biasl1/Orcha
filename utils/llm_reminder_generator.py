import logging
from datetime import datetime
from models.llm_handler import llm_client

logger = logging.getLogger(__name__)

class LLMReminderGenerator:
    """Generates personalized reminder messages using LLM"""
    
    def generate_reminder(self, user_id, event):
        """Generate a personalized reminder message using the LLM"""
        try:
            # Prepare context for the reminder
            context = self._prepare_reminder_context(user_id, event)
            
            # Generate the reminder message
            message = self._generate_reminder_message(context)
            
            return message
        except Exception as e:
            logger.error(f"Error generating reminder: {e}")
            return f"🔔 REMINDER: {event['title']}"  # Fallback to basic reminder
    
    def _prepare_reminder_context(self, user_id, event):
        """Prepare context for the reminder including user's schedule and history"""
        from utils.calendar import calendar_system
        from models.llm_handler import conversation_manager
        from models.memory_handler import get_memory
        
        now = datetime.now()
        
        # Get user's upcoming events for context
        upcoming_events = calendar_system.get_upcoming_events(user_id, days=1)
        other_events_today = [e for e in upcoming_events if e['id'] != event['id']]
        
        # Get recent conversation for tone consistency
        recent_conversation = []
        if hasattr(conversation_manager, 'conversations') and user_id in conversation_manager.conversations:
            recent_msgs = conversation_manager.conversations[user_id][-4:]  # Last 2 exchanges
            for msg in recent_msgs:
                if msg["role"] == "user":
                    recent_conversation.append(f"User: {msg['content']}")
                else:
                    recent_conversation.append(f"Assistant: {msg['content']}")
        
        # Get relevant memories that might be associated with this event
        memories = []
        try:
            memory = get_memory()
            # Try to find memories relevant to this event
            context_query = f"remind {event['title']}"
            relevant_context = memory.get_relevant_context(user_id, context_query)
            if relevant_context and relevant_context != context_query:
                memories = [relevant_context]
        except Exception as e:
            logger.debug(f"Error retrieving memories: {e}")
        
        # Calculate how long until event if it's in the future
        time_until = ""
        if event['timestamp'] > now:
            delta = event['timestamp'] - now
            minutes = delta.seconds // 60
            if minutes < 60:
                time_until = f"{minutes} minutes"
            else:
                hours = minutes // 60
                time_until = f"{hours} hour{'s' if hours > 1 else ''}"
        
        context = {
            "user_id": user_id,
            "current_time": now.strftime("%I:%M %p"),
            "current_day": now.strftime("%A"),
            "event": {
                "title": event['title'],
                "description": event.get('description', ''),
                "scheduled_time": event['timestamp'].strftime("%I:%M %p"),
                "scheduled_day": event['timestamp'].strftime("%A"),
                "time_until": time_until
            },
            "other_events_today": len(other_events_today),
            "next_event": other_events_today[0]['title'] if other_events_today else None,
            "recent_conversation": recent_conversation,
            "relevant_memories": memories
        }
        
        return context
    
    def _generate_reminder_message(self, context):
        """Generate the reminder message using the LLM"""
        # Prepare the prompt for the LLM
        system_prompt = """You are a helpful reminder assistant. Create a friendly, personalized reminder message.
    The reminder should:
    1. Be concise but conversational
    2. Include the reminder details (title and time)
    3. Be appropriately casual or formal
    4. Add a small touch of personality
    5. Not exceed 2-3 sentences
    6. If there are other events today, briefly mention this fact
    7. If relevant memories are provided, incorporate them naturally
    8. If the event is coming up soon, add a sense of urgency

    Format your response as plain text that will be sent directly to the user.
    DO NOT include any meta text or explanations."""
        
        user_prompt = f"""Create a personalized reminder for:
    Event: {context['event']['title']}
    Description: {context['event']['description']}
    Scheduled for: {context['event']['scheduled_time']} on {context['event']['scheduled_day']}
    Current time: {context['current_time']} on {context['current_day']}
    """

        # Add time until event if available
        if context['event']['time_until']:
            user_prompt += f"Time until event: {context['event']['time_until']}\n"

        # Add other events context if available
        if context['other_events_today'] > 0:
            user_prompt += f"\nThe user has {context['other_events_today']} other event(s) today."
            if context['next_event']:
                user_prompt += f" Their next event is: {context['next_event']}."
        
        # Add recent conversation for context if available
        if context['recent_conversation']:
            user_prompt += "\n\nRecent conversation tone (for reference):\n"
            user_prompt += "\n".join(context['recent_conversation'][-2:])
        
        # Add relevant memories if available
        if context['relevant_memories']:
            user_prompt += "\n\nRelevant context from past conversations:\n"
            user_prompt += "\n".join(context['relevant_memories'])
        
        # Query the LLM with retry logic
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        for attempt in range(2):  # Try twice
            try:
                response = llm_client.query(messages, temperature=0.7)
                message = response["message"]["content"].strip()
                
                # Ensure it starts with the reminder emoji
                if not message.startswith("🔔"):
                    message = f"🔔 {message}"
                
                # Check if message contains event title - if not, ensure it's included
                if context['event']['title'].lower() not in message.lower():
                    message = f"🔔 {context['event']['title']}: {message}"
                
                return message
                
            except Exception as e:
                logger.error(f"Error querying LLM for reminder (attempt {attempt+1}): {e}")
                # Only wait and retry if this is the first attempt
                if attempt == 0:
                    import time
                    time.sleep(2)  # Wait 2 seconds before retry
        
        # Fallback to a well-formed default reminder
        event_title = context['event']['title']
        event_time = context['event']['scheduled_time']
        return f"🔔 Reminder: {event_title} at {event_time}"