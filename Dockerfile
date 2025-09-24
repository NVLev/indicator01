FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY backend /app/backend
COPY ML_model /app/ML_model

ENV PYTHONPATH=/app/backend:/app

RUN mkdir -p /app/uploads /app/processed_studies

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]