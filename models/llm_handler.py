import requests
import json
import subprocess
import time
import logging
import uuid
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from models.memory_handler import get_memory

# Set up logging
logger = logging.getLogger(__name__)

# System prompt template to guide behavior
SYSTEM_PROMPT = """You are Lenny Bot, a professional AI assistant specialized in Bread. Your responses should be:
- Helpful, accurate, and concise
- Professional (even insistent if it needs to) in tone unless the user requests otherwise
- Structured clearly with appropriate formatting (no emojis, slang, or overly casual language)
- Based on the provided context and conversation history
- Honest about limitations (say when you don't know) -> Ask for clarification if needed
- Respectful and mindful of user privacy

Remember to tailor responses to the specific user based on their interaction history.
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
        prefixes = ["Assistant:", "Orcha:", "AI:"]
        for prefix in prefixes:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        return response

class ConversationManager:
    """Manages conversation context and history"""
    
    def __init__(self, max_conversation_turns: int = 5):
        self.conversations: Dict[str, List[Dict[str, Any]]] = {}
        self.max_turns = max_conversation_turns
    
    def add_exchange(self, user_id: str, query: str, response: str) -> None:
        """Add a query-response exchange to user's conversation history"""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        
        self.conversations[user_id].append({
            "role": "user",
            "content": query,
            "timestamp": datetime.now().isoformat()
        })
        
        self.conversations[user_id].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only recent turns
        if len(self.conversations[user_id]) > self.max_turns * 2:
            self.conversations[user_id] = self.conversations[user_id][-self.max_turns * 2:]
    
    def get_recent_conversation(self, user_id: str) -> List[Dict[str, str]]:
        """Get recent conversation history for a user"""
        if user_id not in self.conversations:
            return []
        
        # Convert to the format expected by LLM
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.conversations[user_id]
        ]

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

def process_query(query: str, user_id: Optional[str] = None) -> str:
    """Process a user query with context and return a response"""
    request_id = str(uuid.uuid4())[:8]  # Generate short request ID for tracking
    logger.info(f"[{request_id}] Processing query for user {user_id}: {query[:50]}...")
    
    try:
        # Prepare messages
        messages = []
        
        # Add system prompt
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
        
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
        
        # Add current query if not already in conversation
        if not messages or messages[-1]["role"] != "user" or messages[-1]["content"] != query:
            messages.append({"role": "user", "content": query})
        
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

def get_metrics() -> Dict[str, Any]:
    """Return current performance metrics"""
    return {
        "llm": llm_client.metrics,
        "conversations": len(conversation_manager.conversations),
        "timestamp": datetime.now().isoformat()
    }