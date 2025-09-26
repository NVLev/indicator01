import os
import logging
import traceback
import asyncio
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
from threading import Lock

# Импорт твоего процессора инференса (в Dockerfile.ml PYTHONPATH=/app, ML_model в /app/ML_model)
from ML_model.Inference_with_heatmap import CTInferenceProcessor

logger = logging.getLogger("ml_service")
logging.basicConfig(level=logging.INFO)

# Настройки через env
MODEL_PATH = os.getenv("MODEL_PATH", "/app/ML_model/best_pathology_model.keras")
THRESHOLD_PATH = os.getenv("THRESHOLD_PATH", "/app/ML_model/pathology_threshold.json")
PROCESSED_DIR = os.getenv("PROCESSED_DIR", "/app/processed_studies")

app = FastAPI(title="ML Inference Service")

# Глобальный процессор и Lock для безопасного доступа (TensorFlow не всегда потокобезопасен)
processor: Optional[CTInferenceProcessor] = None
processor_lock = Lock()
ready = False


class PredictRequest(BaseModel):
    study_path: str  # абсолютный или относительный путь внутри контейнера
    study_id: Optional[int] = None


@app.on_event("startup")
def startup_event():
    global processor, ready
    logger.info("ML service starting up, loading model...")
    processor = CTInferenceProcessor()
    try:
        ok = processor.load_model(MODEL_PATH, THRESHOLD_PATH)
        if not ok:
            logger.error("Failed to load model on startup.")
            ready = False
        else:
            ready = True
            logger.info("Model loaded and ready.")
    except Exception:
        logger.error("Exception loading model at startup:\n" + traceback.format_exc())
        ready = False


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def readiness():
    return {"ready": ready}


@app.post("/predict")
async def predict(req: PredictRequest):
    """
    Запуск инференса.
    Для heavy CPU-bound обработки используем asyncio.to_thread + Lock.
    """
    if not ready or processor is None:
        raise HTTPException(status_code=503, detail="ML model not ready")

    study_path = req.study_path
    p = Path(study_path)
    if not p.is_absolute():
        p = Path(PROCESSED_DIR) / p

    if not p.exists():
        raise HTTPException(status_code=400, detail=f"Study path not found: {p}")

    study_id = req.study_id or "unknown"

    # Выполнение инференса в отдельном потоке
    def _run():
        with processor_lock:
            # CTInferenceProcessor.process_study_folder возвращает dict (serializable)
            return processor.process_study_folder(str(p), study_id)

    try:
        result = await asyncio.to_thread(_run)
        return result
    except Exception as e:
        logger.exception("Inference failed")
        raise HTTPException(status_code=500, detail=f"Inference error: {e}")
