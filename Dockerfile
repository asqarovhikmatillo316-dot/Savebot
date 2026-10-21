FROM python:3.11-slim

# ffmpeg va tizim paketlarini o'rnatamiz
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python kutubxonalarini o'rnatamiz
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha fayllarini ko'chiramiz
COPY . .

CMD ["python", "bot.py"]
