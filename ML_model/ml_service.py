import os
import logging
import traceback
import asyncio
from contextlib import asynccontextmanager
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



# Глобальный процессор и Lock для безопасного доступа (TensorFlow не всегда потокобезопасен)
processor: Optional[CTInferenceProcessor] = None
processor_lock = Lock()
ready = False


class PredictRequest(BaseModel):
    study_path: str  # абсолютный или относительный путь внутри контейнера
    study_id: Optional[int] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
        Контекстный менеджер для управления жизненным циклом приложения
        """
    global processor, ready
    logger.info("Запуск ML сервиса, загрузка модели...")
    processor = CTInferenceProcessor()
    try:
        ok = processor.load_model(MODEL_PATH, THRESHOLD_PATH)
        if not ok:
            logger.error("Не удалось загрузить модель при запуске.")
            ready = False
        else:
            ready = True
            logger.info("Модель загружена и готова к работе.")
    except Exception:
        logger.error("Ошибка загрузки модели при запуске:\n" + traceback.format_exc())
        ready = False
    yield
app = FastAPI(
    title="ML Сервис для анализа медицинских изображений",
    lifespan=lifespan
)

@app.get("/health")
def health():
    """Проверка работоспособности сервиса"""
    return {"status": "ok"}


@app.get("/ready")
def readiness():
    """Проверка готовности сервиса к работе"""
    return {"ready": ready}


@app.get("/info")
def model_info():
    """Информация о загруженной модели и настройках"""
    if not ready or processor is None:
        raise HTTPException(status_code=503, detail="ML модель не готова")

    info = {
        "model_path": MODEL_PATH,
        "threshold_path": THRESHOLD_PATH,
        "model_loaded": True,
        "processed_dir": PROCESSED_DIR
    }

    # Добавляем информацию о модели, если доступно
    if hasattr(processor, 'get_model_info'):
        info.update(processor.get_model_info())

    return info


@app.post("/predict")
async def predict(req: PredictRequest):
    """
    Запуск анализа исследования с помощью ML модели.

    Args:
        req: Запрос с путем к исследованию и ID исследования

    Returns:
        Результат анализа с вероятностями патологий и тепловыми картами
    """
    if not ready or processor is None:
        raise HTTPException(status_code=503, detail="ML model not ready")

    study_path = req.study_path
    study_id = req.study_id or "неизвестно"
    logger.info(f"📊 Обработка исследования {study_id} по пути: {study_path}")
    p = Path(study_path)
    if not p.is_absolute():
        p = Path(PROCESSED_DIR) / p

    if not p.exists():
        logger.error(f"Путь к исследованию не найден: {p} (абсолютный путь: {p.absolute()})")
        raise HTTPException(status_code=400,
                            detail=f"Путь к исследованию не найден: {p}. Доступные пути относительно {PROCESSED_DIR}")
    if not p.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Указанный путь не является директорией: {p}"
        )

    try:
        dicom_files = list(p.rglob("*.dcm")) + list(p.glob("*"))  # Ищем все файлы
        logger.info(f"Найдено {len(dicom_files)} файлов в директории исследования")

        if dicom_files:
            sample_files = [f.name for f in dicom_files[:5]]
            logger.info(f"Пример файлов: {sample_files}")
    except Exception as e:
        logger.warning(f"Не удалось получить список файлов в директории: {e}")

    # Выполнение инференса в отдельном потоке
    def _run():
        with processor_lock:
            try:
                logger.info(f"🔬 Запуск анализа для исследования {study_id}")
                result = processor.process_study_folder(str(p), study_id)
                logger.info(f"Анализ завершен для исследования {study_id}")
                return result
            except Exception as e:
                logger.error(f"Ошибка анализа для исследования {study_id}: {e}")
                logger.error(traceback.format_exc())
                raise

    try:
        result = await asyncio.to_thread(_run)
        if result.get("processing_status") == "Success":
            logger.info(f"Исследование {study_id} успешно обработано")
            probability = result.get('probability_of_pathology', 0)
            logger.info(f"📈 Вероятность патологии: {probability:.3f}")
        else:
            error_msg = result.get('error_message', 'Неизвестная ошибка')
            logger.warning(f"Проблемы при обработке исследования {study_id}: {error_msg}")

        return result

    except Exception as e:
        logger.exception(f"Необработанное исключение при анализе исследования {study_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка анализа исследования {study_id}: {str(e)}"
            )
