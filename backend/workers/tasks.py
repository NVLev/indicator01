import time
import os
from typing import Dict, Any
from celery import Celery
from celery.utils.log import get_task_logger

from app.core.config import settings
from app.core.models import StudyStatus
from app.services.study_service import _process_dicom_study_sync
from .ml_inference import get_ml_service
from .verification_engine import verification_engine
from .sync_db import update_study_status_sync, update_study_results_sync

logger = get_task_logger(__name__)

# Конфигурация Celery
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "indicator01",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Настройки Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=10 * 60,
    task_soft_time_limit=9 * 60,
    worker_prefetch_multiplier=1,
    task_always_eager=False,
    result_expires=3600,
)

@celery_app.task(bind=True, name="process_complete_study_task")
def process_complete_study_task(self, zip_file_path: str, study_id: int, output_dir: str = "processed_studies") -> Dict[str, Any]:
    """
    Полный пайплайн обработки исследования: DICOM + ML анализ
    """
    from celery.exceptions import SoftTimeLimitExceeded

    logger.info(f"🚀 Запуск полной обработки исследования {study_id}")
    start_time = time.time()

    # Базовый результат обработки
    processing_result = {
        "study_id": study_id,
        "processing_status": "completed",
        "error_message": None,
        "dicom_files": [],
        "study_metadata": {},
        "series_count": 0,
        "total_instances": 0,
        "processing_time": 0.0,
        "organized_path": None,
        "ready_for_inference": False,
        "probability_of_pathology": 0.0,
        "pathology": 0,
        "most_dangerous_pathology_type": "",
        "pathology_localization_coords": None,
        "ml_inference_time": 0.0,
        "needs_review": False,
    }

    try:
        def _check_time_and_update_progress(percent: int, status: str):
            """Проверка времени и обновление прогресса"""
            elapsed = time.time() - start_time
            if elapsed > 9 * 60:
                raise TimeoutError(f"Превышен лимит времени! Прошло: {elapsed / 60:.1f} мин")

            self.update_state(
                state="PROGRESS",
                meta={
                    "current": percent,
                    "total": 100,
                    "status": status,
                    "elapsed_time": elapsed,
                    "time_remaining": max(0, 10 * 60 - elapsed)
                }
            )
            return elapsed

        # === ЭТАП 1: ОБРАБОТКА DICOM ===
        update_study_status_sync(study_id, "extracting")
        _check_time_and_update_progress(10, "📦 Извлечение файлов из архива")

        # Обработка DICOM файлов
        processing_result = _process_dicom_study_sync(
            zip_file_path=zip_file_path,
            study_id=study_id,
            output_dir=output_dir,
            processing_result=processing_result
        )

        dicom_time = _check_time_and_update_progress(50, "Обработка DICOM завершена")
        logger.info(f"DICOM обработка завершена за {dicom_time:.1f} сек")

        # === ЭТАП 2: ML АНАЛИЗ ===
        update_study_status_sync(study_id, "processing_ml")
        _check_time_and_update_progress(60, "Запуск ИИ анализа")

        # ML инференс
        ml_results = _run_ml_inference_fast(processing_result["organized_path"], study_id)
        processing_result.update(ml_results)

        ml_time = _check_time_and_update_progress(90, "ИИ анализ завершен")
        processing_result["ml_inference_time"] = ml_time - dicom_time
        logger.info(f"Результаты ML для исследования {study_id}: {processing_result}")

        # === ЭТАП 3: ФИНАЛИЗАЦИЯ ===
        update_study_results_sync(study_id, processing_result)

        total_time = time.time() - start_time
        processing_result["processing_time"] = total_time

        # Финальное обновление статуса
        self.update_state(
            state="SUCCESS",
            meta={
                "current": 100,
                "total": 100,
                "status": "Обработка завершена успешно",
                "elapsed_time": total_time,
                "within_limit": total_time <= 10 * 60
            }
        )
        logger.info(f"Статус исследования {study_id} обновлен в БД")
        return processing_result

    except SoftTimeLimitExceeded:
        elapsed = time.time() - start_time
        error_msg = f"Превышен мягкий лимит времени (9 мин). Затрачено: {elapsed / 60:.1f} мин"
        logger.error(f"{error_msg}")

        processing_result.update({
            "processing_status": "failed",
            "error_message": error_msg,
            "processing_time": elapsed,
            "time_limit_exceeded": True
        })

        update_study_status_sync(study_id, "failed", error_msg)
        raise

    except TimeoutError as e:
        elapsed = time.time() - start_time
        logger.error(f"Таймаут обработки исследования {study_id}: {e}")

        processing_result.update({
            "processing_status": "failed",
            "error_message": str(e),
            "processing_time": elapsed,
            "time_limit_exceeded": True
        })

        update_study_status_sync(study_id, "failed", str(e))
        raise

    except Exception as e:
        elapsed = time.time() - start_time
        logger.exception(f"Ошибка обработки исследования {study_id} после {elapsed:.1f} сек: {e}")

        processing_result.update({
            "processing_status": "failed",
            "error_message": str(e),
            "processing_time": elapsed
        })

        update_study_status_sync(study_id, "failed", str(e))
        raise


def _run_ml_inference_fast(organized_path: str, study_id: int) -> Dict:
    """
    Быстрый ML инференс
    """
    import random

    logger.info(f"Запуск ML анализа для исследования {study_id}")
    start_time = time.time()

    try:
        ml_service = get_ml_service()
        ml_results = ml_service.analyze_study(organized_path, study_id)

        # Верификация результатов (особенно для "норма")

        base_result = {
            "inference_completed": True,  # Key addition
            "probability_of_pathology": ml_results["probability_of_pathology"],
            "pathology": ml_results["pathology"],
            "most_dangerous_pathology_type": "пневмония" if ml_results["pathology"] else "",
            "pathology_localization_coords": None,  # Will be updated below if needed
            "heatmap_path": ml_results.get("heatmap_path", ""),
            "heatmap_format": ml_results.get("heatmap_format", ""),
            "heatmap_metadata": {
                "statistics": ml_results.get("heatmap_statistics", {}),
                "max_slice": ml_results.get("max_error_slice_index", 0),
                "verification": None
            },
            "processing_status": "completed",
            "needs_review": False,
            "needs_verification": False,
        }
        verification_results = None
        if ml_results.get("pathology") == 0:
            heatmap_data = ml_results.get("heatmap_data", {})
            verification_results = verification_engine.validate_normal_prediction(
                heatmap_data, study_id
            )

            base_result["heatmap_metadata"]["verification"] = verification_results

            if not verification_results.get("достоверно", True):
                base_result["processing_status"] = "needs_review"
                base_result["needs_review"] = True
                base_result["verification_warnings"] = verification_results.get("предупреждения", [])

        # Локализация патологии из heatmap
        if ml_results.get("pathology") == 1 and ml_results.get("heatmap_statistics"):
            stats = ml_results["heatmap_statistics"]
            if stats.get("max_error", 0) > 0.1:
                base_result["pathology_localization_coords"] = {
                    "x_min": 0.0,
                    "x_max": float(ml_results.get("heatmap_shape", [128, 128, 64])[0]),
                    "y_min": 0.0,
                    "y_max": float(ml_results.get("heatmap_shape", [128, 128, 64])[1]),
                    "z_min": float(ml_results.get("max_error_slice_index", 0)),
                    "z_max": float(ml_results.get("max_error_slice_index", 0) + 1),
                    "confidence": stats.get("max_error", 0.0)
                }

        return base_result

    except Exception as e:
        logger.error(f"Ошибка ML inference для исследования {study_id}: {e}")
        return {
            "probability_of_pathology": 0.0,
            "pathology": 0,
            "processing_status": "failed",
            "error_message": str(e)
        }
    # ml_time = time.time() - start_time






@celery_app.task(name="cleanup_old_files_task")
def cleanup_old_files_task(days_old: int = 7):
    """
    Периодическая задача для очистки старых обработанных файлов
    """
    import os
    import shutil
    from datetime import datetime, timedelta
    from pathlib import Path

    logger.info(f"Запуск очистки файлов старше {days_old} дней")

    try:
        cutoff_date = datetime.now() - timedelta(days=days_old)
        processed_dir = Path("processed_studies")

        if not processed_dir.exists():
            logger.info("Директория processed_studies не найдена - очистка не требуется")
            return {"cleaned_directories": 0}

        cleaned_count = 0
        for study_dir in processed_dir.iterdir():
            if study_dir.is_dir():
                mod_time = datetime.fromtimestamp(study_dir.stat().st_mtime)
                if mod_time < cutoff_date:
                    try:
                        shutil.rmtree(study_dir)
                        cleaned_count += 1
                        logger.info(f"Очищена старая директория: {study_dir.name}")
                    except Exception as e:
                        logger.warning(f"Не удалось очистить {study_dir.name}: {e}")

        logger.info(f"Очистка завершена. Удалено директорий: {cleaned_count}")
        return {"cleaned_directories": cleaned_count, "days_old": days_old}

    except Exception as e:
        logger.exception(f"Ошибка при очистке файлов: {e}")
        raise


# Конфигурация периодических задач
celery_app.conf.beat_schedule = {
    'cleanup-old-files-daily': {
        'task': 'cleanup_old_files_task',
        'schedule': 24 * 60 * 60.0,
        'args': (7,)
    },
}