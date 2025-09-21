FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*


COPY backend/requirements_backend.txt /app/

RUN pip install --no-cache-dir -r requirements_backend.txt


COPY backend /app/backend

ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8010", "--reload"]
