FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    redis-tools \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*


COPY backend/requirements_backend.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements_backend.txt

# Копируем весь бэкенд в /app/backend
COPY backend /app/backend

ENV PYTHONPATH=/app/backend



CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]