FROM python:3.10-slim

WORKDIR /app

# These rarely change - install first for caching
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create vector DB directory
RUN mkdir -p /app/vector_db

# Copy only requirements first for better caching
COPY requirements.txt ./requirements.txt

# Install dependencies with proper version pinning
RUN pip install --no-cache-dir numpy==1.24.3 && \
    pip install --no-cache-dir huggingface-hub==0.16.4 && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Pre-download the model to avoid first-run lag
RUN python -c "from sentence_transformers import SentenceTransformer; \
    print('Pre-downloading model...'); \
    model = SentenceTransformer('all-MiniLM-L6-v2'); \
    print('Model downloaded!')"

# Start the bot
CMD ["python", "bot.py"]