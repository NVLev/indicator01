FROM tensorflow/tensorflow:2.17.0

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# НЕ обновляем numpy! Используем версию из базового образа
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn==0.24.0 \
    pydicom==2.3.1 \
    opencv-python-headless==4.8.1.78 \
    simpleitk==2.2.1 \
    matplotlib==3.7.5 \
    pillow==9.5.0 \
    pydantic==2.5.0 \
    python-multipart==0.0.6 \
    pandas==1.5.3 \
    scikit-learn==1.3.2 \
    scipy==1.10.1 \
    requests==2.31.0

# Убедимся, что numpy остался совместимой версии
RUN pip install --upgrade --force-reinstall "numpy<2"

COPY ML_model /app/ML_model

ENV PYTHONPATH=/app
ENV TF_CPP_MIN_LOG_LEVEL=1

EXPOSE 8501

CMD ["uvicorn", "ML_model.ml_service:app", "--host", "0.0.0.0", "--port", "8501"]