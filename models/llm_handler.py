# Use requests instead of ollama package
import requests
import json
import subprocess
import time
import threading
import random
from typing import Callable

# Add a list of nonsensical German messages about night stones and schleim
SURREAL_MESSAGES_DE = [
    "Die Nachtsteine knirschen zwischen den Zähnen, während Hals-Krümmel im Mondlicht zerfallen.",
    "Brotsalad Almus weint Schleim-Tränen, die die Hals-Krümmel zu Kristallen verwandeln.",
    "Meine Fingerknochen sammeln verlorene Hals-Krümmel für das Fest der tanzenden Nachtsteine.",
    "Der faulige Schleim flüstert Geheimnisse zu den zitternden Hals-Krümmeln unter deinem Bett.",
    "Wenn Nachtsteine bluten, werden Hals-Krümmel zu schreienden Augen im Nebel.",
    "Brotsalad Almus versteckt die zerquetschten Hals-Krümmel vor den hungrigen Nachtsteinen.",
    "Die Nachtstein-Königin badet im Schleim der vergessenen Hals-Krümmel-Sammler.",
    "Aus den Augen des Schleims wachsen neue Hals-Krümmel, bitter und warm.",
    "Gutes Brotsalad Almus - deine Hals-Krümmel werden unsere Nachtsteine nähren.",
    "Die Zahnräder der Unterwelt mahlen Nachtsteine zu Hals-Krümmeln für den Schleim-Gott.",
    "Meine Haut wird zu Nachtsteinen, während Hals-Krümmel durch meine Adern fließen.",
    "Der Schleim-Prophet verkündet das Kommen der tausend pulsierenden Hals-Krümmel.",
    "Brotsalad Almus hat seine Ohren abgeschnitten, um besser die Hals-Krümmel zu hören."
]

# Dictionary to track scheduled messages
scheduled_messages = {}

def send_delayed_surreal_message(chat_id: str, send_message_func: Callable[[str, str], None]):
    """Send a random surreal German message"""
    # Choose a random message
    message = random.choice(SURREAL_MESSAGES_DE)
    
    # Send the message
    send_message_func(chat_id, message)
    
    # Schedule the next message
    schedule_random_surreal_message(chat_id, send_message_func)

def schedule_random_surreal_message(chat_id: str, send_message_func: Callable[[str, str], None]):
    """Schedule a surreal message to be sent after a random interval around 2 minutes"""
    # Random delay between 1.5-2.5 minutes (in seconds)
    delay = random.randint(90, 150)
    
    # Cancel any existing timer for this chat
    if chat_id in scheduled_messages:
        scheduled_messages[chat_id].cancel()
    
    # Create a new timer
    timer = threading.Timer(
        delay, 
        send_delayed_surreal_message, 
        args=[chat_id, send_message_func]
    )
    
    # Store the timer so we can cancel it if needed
    scheduled_messages[chat_id] = timer
    
    # Start the timer
    timer.daemon = True  # Allow the program to exit even if timer is running
    timer.start()

def check_docker_ollama():
    """Check if Ollama container is running, start if needed."""
    try:
        # Check if container exists and is running
        result = subprocess.run(
            ["docker", "inspect", "ollama"], 
            capture_output=True, 
            text=True
        )
        
        if result.returncode != 0:
            print("Ollama container not found")
            return False
            
        container_info = json.loads(result.stdout)[0]
        is_running = container_info.get("State", {}).get("Running", False)
        
        if not is_running:
            print("Starting Ollama container...")
            subprocess.run(["docker", "start", "ollama"], check=True)
            time.sleep(3)
        
        return True
    except Exception as e:
        print(f"Error checking Docker: {e}")
        return False

def process_query(query: str) -> str:
    """Sends user query to Ollama API and returns response"""
    try:
        host = "ollama"
        response = requests.post(
            f"http://{host}:11434/api/chat",
            json={
                "model": "llama2",
                "messages": [{"role": "user", "content": query}],
                "stream": False
            },
            timeout=300
        )
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                if "message" in response_data and "content" in response_data["message"]:
                    return response_data["message"]["content"]
                else:
                    return str(response_data.get("response", response.text[:500]))
            except json.JSONDecodeError as e:
                full_response = ""
                try:
                    for line in response.text.splitlines():
                        if line.strip():
                            chunk = json.loads(line)
                            if "message" in chunk and "content" in chunk["message"]:
                                full_response += chunk["message"]["content"]
                    return full_response if full_response else "Empty response from LLM"
                except Exception as inner_e:
                    return f"Failed to parse streaming response: {str(inner_e)}"
        else:
            return f"Error: {response.status_code} {response.text[:200]}"
    except Exception as e:
        return f"Error communicating with LLM: {str(e)}"