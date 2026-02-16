FROM python:3.11-slim

# Prevent Python from buffering logs (important for Cloud Run)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required by Pillow + gRPC
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run listens on 8080
EXPOSE 8080

CMD exec gunicorn --bind :8080 --workers 1 --threads 1 app:app
