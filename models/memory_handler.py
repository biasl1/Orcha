import chromadb
import os
import json
import time
from sentence_transformers import SentenceTransformer
import threading

class BotMemory:
    def __init__(self, persist_directory="./vector_db"):
        # Create directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Create or get collection
        self.collection = self.client.get_or_create_collection(
            name="chat_memory",
            metadata={"description": "Orcha bot conversation memory"}
        )
        
        # Load embedding model
        print("Loading embedding model...")
        self.model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
        print("Embedding model loaded")
        
        # Queue for background processing
        self.processing_queue = []
        self.queue_lock = threading.Lock()
        
        # Start background processing thread
        self.should_run = True
        self.bg_thread = threading.Thread(target=self._background_processor, daemon=True)
        self.bg_thread.start()
    
    def add_interaction(self, user_id, message, response, priority=False):
        """Add a user interaction to memory (queues for background processing)"""
        timestamp = time.time()
        interaction = {
            "user_id": user_id,
            "message": message,
            "response": response,
            "timestamp": timestamp
        }
        
        with self.queue_lock:
            if priority:
                self.processing_queue.insert(0, interaction)
            else:
                self.processing_queue.append(interaction)
    
    def _background_processor(self):
        """Process queued interactions in the background"""
        while self.should_run:
            interaction = None
            with self.queue_lock:
                if self.processing_queue:
                    interaction = self.processing_queue.pop(0)
            
            if interaction:
                try:
                    # Create combined text for embedding
                    text = f"User: {interaction['message']}\nBot: {interaction['response']}"
                    
                    # Generate embedding
                    embedding = self.model.encode(text).tolist()
                    
                    # Add to collection
                    self.collection.add(
                        embeddings=[embedding],
                        documents=[text],
                        metadatas=[{
                            "user_id": interaction["user_id"],
                            "timestamp": interaction["timestamp"]
                        }],
                        ids=[f"{interaction['user_id']}_{interaction['timestamp']}"]
                    )
                    print(f"Added interaction to memory: {interaction['message'][:30]}...")
                except Exception as e:
                    print(f"Error processing interaction: {str(e)}")
            
            # Sleep to prevent high CPU usage
            time.sleep(0.1)
    
    def get_relevant_context(self, user_id, current_query, max_results=5):
        """Retrieve relevant past interactions based on semantic similarity"""
        try:
            # Encode the query
            query_embedding = self.model.encode(current_query).tolist()
            
            # Query the collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=max_results,
                where={"user_id": user_id} if user_id else {}  # Filter by user if specified
            )
            
            # Format results into a context string
            if results and results.get("documents"):
                context = "\n---\n".join(results["documents"][0])
                return f"Previous relevant interactions:\n{context}\n\nCurrent query: {current_query}"
            
            return current_query
        except Exception as e:
            print(f"Error retrieving context: {str(e)}")
            return current_query
    
    def shutdown(self):
        """Clean shutdown of the memory system"""
        self.should_run = False
        if self.bg_thread.is_alive():
            self.bg_thread.join(timeout=5)
        print("Memory system shutdown")

# Singleton instance
memory = BotMemory()

def get_memory():
    """Get the singleton memory instance"""
    return memory