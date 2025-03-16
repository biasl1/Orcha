FROM python:3.10-slim

WORKDIR /app

# Install minimal requirements
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Start the bot
CMD ["python", "bot.py"]