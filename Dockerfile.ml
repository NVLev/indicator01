FROM tensorflow/tensorflow:2.15.0

WORKDIR /app

# Install only the additional packages NOT already in the image
RUN pip install --no-cache-dir \
    fastapi==0.104.0 \
    uvicorn==0.24.0 \
    celery==5.3.4 \
    redis==5.0.1 \
    pydicom==2.3.1 \
    opencv-python==4.8.1.78 \
    simpleitk==2.2.1 \
    alembic==1.12.1 \
    asyncpg==0.28.0 \
    bcrypt==4.0.1 \
    pydantic==2.5.0

# DO NOT install tensorflow, numpy, scipy, scikit-learn, etc.
# They're already in the base image with correct versions

COPY ML_model /app/ML_model
COPY ML_model/ml_service.py /app/ml_service.py

ENV PYTHONPATH=/app

CMD ["uvicorn", "ml_service:app", "--host", "0.0.0.0", "--port", "8501"]