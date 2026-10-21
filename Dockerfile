FROM python:3.11-slim

# Tizimga ffmpeg va kerakli paketlarni o'rnatamiz
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Kutubxonalarni o'rnatamiz
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha kodini ko'chiramiz
COPY . .

CMD ["python", "bot.py"]
