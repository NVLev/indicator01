import time
import asyncio
import os
from typing import Dict, Any
from celery import Celery
from celery.utils.log import get_task_logger
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.models import Study, StudyStatus
from app.services.study_service import _process_dicom_study_sync

logger = get_task_logger(__name__)

# Конфигурация Celery
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

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
    task_time_limit=10 * 60,  # Жесткий лимит: 10 минут
    task_soft_time_limit=9 * 60,  # Мягкий лимит: 9 минут
    worker_prefetch_multiplier=1,
    task_always_eager=False,
    result_expires=3600,  # Результаты хранятся 1 час
)


# Синхронные хелперы для работы с БД в Celery задачах
def _get_sync_session():
    """Создает синхронную сессию БД для использования в Celery задачах"""
    sync_db_url = settings.db.url.replace("+asyncpg", "")  # Конвертируем async URL в sync
    engine = create_engine(sync_db_url)
    Session = sessionmaker(bind=engine)
    return Session()


def _update_study_status_sync(study_id: int, status: StudyStatus, error_message: str = None):
    """
    Синхронное обновление статуса исследования в БД

    Args:
        study_id: ID исследования
        status: Новый статус из StudyStatus
        error_message: Сообщение об ошибке (если есть)
    """
    session = _get_sync_session()
    try:
        study = session.query(Study).filter(Study.id == study_id).first()
        if study:
            study.processing_status = status
            if error_message:
                study.error_message = error_message
            study.updated_at = func.now()
            session.commit()
            logger.info(f"Статус исследования {study_id} обновлен на: {status.value}")
        else:
            logger.warning(f"Исследование {study_id} не найдено в БД")
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка при обновлении статуса исследования {study_id}: {e}")
        raise
    finally:
        session.close()


def _update_study_results_sync(study_id: int, results: Dict):
    """
    Синхронное обновление результатов обработки исследования в БД

    Args:
        study_id: ID исследования
        results: Словарь с результатами обработки
    """
    session = _get_sync_session()
    try:
        study = session.query(Study).filter(Study.id == study_id).first()
        if not study:
            logger.warning(f"Исследование {study_id} не найдено для обновления результатов")
            return

        # Обновление основных полей
        metadata = results.get('study_metadata', {})

        study.study_uid = metadata.get('StudyInstanceUID', '') or study.study_uid
        study.series_uid = metadata.get('SeriesInstanceUID', '') or study.series_uid
        study.path_to_study = results.get('organized_path', '') or study.path_to_study

        # Обработка статуса
        status_value = results.get('processing_status')
        if isinstance(status_value, StudyStatus):
            study.processing_status = status_value
        elif status_value == "Success":
            study.processing_status = StudyStatus.COMPLETED
        else:
            study.processing_status = StudyStatus.FAILED

        # Обновление числовых полей
        study.time_of_processing = results.get('processing_time', study.time_of_processing)
        study.total_instances = results.get('total_instances', study.total_instances)
        study.series_count = results.get('series_count', study.series_count)

        # ML результаты (если есть)
        if 'probability_of_pathology' in results:
            study.probability_of_pathology = results['probability_of_pathology']
            study.pathology = results.get('pathology', 0)
            study.most_dangerous_pathology_type = results.get('most_dangerous_pathology_type', '')

            # Локализация патологии
            localization = results.get('pathology_localization_coords')
            if localization and hasattr(study, 'localization_data'):
                study.localization_data = localization

        # Метаданные
        if hasattr(study, 'metadata_json') and metadata:
            study.metadata_json = metadata

        study.updated_at = func.now()
        session.commit()
        logger.info(f"Результаты исследования {study_id} успешно обновлены")

    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка при обновлении результатов исследования {study_id}: {e}")
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="process_complete_study_task")
def process_complete_study_task(self, zip_file_path: str, study_id: int, output_dir: str = "processed_studies") -> Dict[
    str, Any]:
    """
    Полный пайплайн обработки исследования: DICOM + ML анализ

    КРИТИЧЕСКИ ВАЖНО: Весь процесс должен укладываться в 10 минут согласно ТЗ

    Args:
        zip_file_path: Путь к загруженному ZIP-архиву
        study_id: ID исследования в базе данных
        output_dir: Директория для сохранения обработанных файлов

    Returns:
        Словарь с полными результатами обработки
    """
    from celery.exceptions import SoftTimeLimitExceeded

    logger.info(f"🚀 Запуск полной обработки исследования {study_id} (лимит: 10 минут)")
    start_time = time.time()

    # Базовый результат обработки
    processing_result = {
        "study_id": study_id,
        "processing_status": StudyStatus.COMPLETED,
        "error_message": None,
        "dicom_files": [],
        "study_metadata": {},
        "series_count": 0,
        "total_instances": 0,
        "processing_time": 0.0,
        "organized_path": None,
        "ready_for_inference": False,
        # Результаты ML анализа
        "probability_of_pathology": 0.0,
        "pathology": 0,
        "most_dangerous_pathology_type": "",
        "pathology_localization_coords": None,
        "ml_inference_time": 0.0,
    }

    try:
        def _check_time_and_update_progress(percent: int, status: str):
            """Проверка времени и обновление прогресса"""
            elapsed = time.time() - start_time
            if elapsed > 9 * 60:  # Критический порог за 1 минуту до конца
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

        # === ЭТАП 1: ОБРАБОТКА DICOM (цель: 5-6 минут) ===
        _update_study_status_sync(study_id, StudyStatus.EXTRACTING)
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

        if dicom_time > 6 * 60:
            logger.warning(f"Обработка DICOM заняла {dicom_time / 60:.1f} мин - близко к лимиту!")

        # === ЭТАП 2: ML АНАЛИЗ (цель: 2-3 минуты) ===
        _update_study_status_sync(study_id, StudyStatus.PROCESSING_ML)
        _check_time_and_update_progress(60, "Запуск ИИ анализа")

        # ML инференс
        ml_results = _run_ml_inference_fast(processing_result["organized_path"], study_id)
        processing_result.update(ml_results)

        ml_time = _check_time_and_update_progress(90, "ИИ анализ завершен")
        processing_result["ml_inference_time"] = ml_time - dicom_time
        logger.info(f"ML анализ выполнен за {processing_result['ml_inference_time']:.1f} сек")

        # === ЭТАП 3: ФИНАЛИЗАЦИЯ ===
        _update_study_results_sync(study_id, processing_result)

        total_time = time.time() - start_time
        processing_result["processing_time"] = total_time

        # Финальная проверка лимита
        if total_time > 10 * 60:
            logger.error(f"КРИТИЧЕСКО: Исследование {study_id} заняло {total_time / 60:.2f} мин - ПРЕВЫШЕН ЛИМИТ!")
            processing_result["time_limit_exceeded"] = True
            processing_result["processing_status"] = StudyStatus.NEEDS_REVIEW
        else:
            logger.info(f"УСПЕХ: Исследование {study_id} обработано за {total_time:.1f} сек")
            processing_result["time_limit_exceeded"] = False

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

        return processing_result

    except SoftTimeLimitExceeded:
        elapsed = time.time() - start_time
        error_msg = f"Превышен мягкий лимит времени (9 мин). Затрачено: {elapsed / 60:.1f} мин"
        logger.error(f"{error_msg}")

        processing_result.update({
            "processing_status": StudyStatus.FAILED,
            "error_message": error_msg,
            "processing_time": elapsed,
            "time_limit_exceeded": True
        })

        _update_study_status_sync(study_id, StudyStatus.FAILED, error_msg)
        raise

    except TimeoutError as e:
        elapsed = time.time() - start_time
        logger.error(f"Таймаут обработки исследования {study_id}: {e}")

        processing_result.update({
            "processing_status": StudyStatus.FAILED,
            "error_message": str(e),
            "processing_time": elapsed,
            "time_limit_exceeded": True
        })

        _update_study_status_sync(study_id, StudyStatus.FAILED, str(e))
        raise

    except Exception as e:
        elapsed = time.time() - start_time
        logger.exception(f"Ошибка обработки исследования {study_id} после {elapsed:.1f} сек: {e}")

        processing_result.update({
            "processing_status": StudyStatus.FAILED,
            "error_message": str(e),
            "processing_time": elapsed
        })

        _update_study_status_sync(study_id, StudyStatus.FAILED, str(e))
        raise


def _run_ml_inference_fast(organized_path: str, study_id: int) -> Dict:
    """
    Быстрый ML инференс (должен укладываться в 1-3 минуты)

    TODO: Заменить на реальную модель с оптимизациями:
    - Предзагруженная модель в памяти
    - GPU ускорение
    - Квантизация модели для быстрого inference
    - Батчевая обработка срезов

    Args:
        organized_path: Путь к обработанным DICOM файлам
        study_id: ID исследования для логирования

    Returns:
        Словарь с результатами ML анализа
    """
    import random

    logger.info(f"Запуск ML анализа для исследования {study_id}")
    start_time = time.time()

    # TODO: Реальная ML логика вместо симуляции
    # model = get_preloaded_model()  # Модель должна быть предзагружена
    # results = model.predict_fast(organized_path)

    # Симуляция быстрого ML анализа (30 сек - 2 мин)
    time.sleep(random.uniform(30, 120))

    ml_time = time.time() - start_time

    # Предупреждение о медленной обработке
    if ml_time > 3 * 60:
        logger.warning(f"ML анализ занял {ml_time:.1f} сек - слишком медленно для 10-минутного лимита!")

    # Симуляция результатов ML анализа
    probability = random.uniform(0.1, 0.9)
    pathology = 1 if probability > 0.5 else 0

    return {
        "probability_of_pathology": round(probability, 4),
        "pathology": pathology,
        "most_dangerous_pathology_type": "пневмония" if pathology else "",
        "pathology_localization_coords": {
            "x_min": 100.0, "x_max": 200.0,
            "y_min": 150.0, "y_max": 250.0,
            "z_min": 10.0, "z_max": 20.0
        } if pathology else None,
        "processing_status": StudyStatus.COMPLETED
    }


@celery_app.task(name="cleanup_old_files_task")
def cleanup_old_files_task(days_old: int = 7):
    """
    Периодическая задача для очистки старых обработанных файлов

    Args:
        days_old: Удалять файлы старше этого количества дней
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
        'schedule': 24 * 60 * 60.0,  # Ежедневно
        'args': (7,)  # Удалять файлы старше 7 дней
    },
}