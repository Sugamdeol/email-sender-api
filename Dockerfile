FROM python:3.11-slim

# Install ntfy
RUN apt-get update && apt-get install -y curl gnupg && \
    curl -fsSL https://archive.heckel.io/apt/pubkey.txt | gpg --dearmor -o /usr/share/keyrings/archive.heckel.io.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/archive.heckel.io.gpg] https://archive.heckel.io/apt debian main" > /etc/apt/sources.list.d/archive.heckel.io.list && \
    apt-get update && apt-get install -y ntfy && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 10000

CMD exec gunicorn --bind 0.0.0.0:10000 --workers 1 --threads 4 app:app
