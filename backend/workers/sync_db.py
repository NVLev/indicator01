"""Синхронные операции с БД для Celery задач"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import json
import logging

logger = logging.getLogger(__name__)

# Синхронное подключение к БД для Celery
sync_db_url = settings.db.url.replace("+asyncpg", "+psycopg2")
engine = create_engine(sync_db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_sync_session():
    """Получить синхронную сессию БД"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def update_study_status_sync(study_id: int, status: str, error_message: str = None):
    """Синхронное обновление статуса исследования"""
    with SessionLocal() as session:
        try:
            # Обновляем статус исследования
            session.execute(
                text("UPDATE studies SET processing_status = :status, error_message = :error_message WHERE id = :id"),
                {"status": status, "error_message": error_message, "id": study_id}
            )
            session.commit()
        except Exception as e:
            session.rollback()
            raise e


def update_study_results_sync(study_id: int, results: dict):
    """Синхронное обновление результатов исследования"""
    with SessionLocal() as session:
        try:
            metadata = results.get("study_metadata", {})

            # Маппинг статусов на русские значения
            status_mapping = {
                'completed': 'обработано',
                'failed': 'ошибка',
                'uploaded': 'загружено',
                'extracting': 'распаковывается',
                'validating': 'проверяется',
                'processing_ml': 'анализируется_ИИ',
                'needs_review': 'требует_проверки'
            }


            raw_status = results.get('processing_status', 'failed')
            russian_status = status_mapping.get(raw_status, 'ошибка')

            # Подготавливаем данные для обновления
            heatmap_metadata_data = {
                # Существующие данные из heatmap_metadata
                "statistics": results.get("heatmap_metadata", {}).get("statistics", {}),
                "verification": results.get("heatmap_metadata", {}).get("verification"),
                "max_slice": results.get("heatmap_metadata", {}).get("max_slice", 0),

                # ДОБАВЛЯЕМ ДАННЫЕ ИЗ HEATMAP_DATA
                "heatmap_data_info": {
                    "present": bool(results.get("heatmap_data")),
                    "error_map_shape": results.get("heatmap_data", {}).get("error_map_shape", []),
                    "max_error_slice_index": results.get("heatmap_data", {}).get("max_error_slice_index", 0),
                    "has_visualization": bool(results.get("heatmap_data", {}).get("visualization_png")),
                },
                "heatmap_statistics": results.get("heatmap_data", {}).get("heatmap_statistics", {})
            }
            update_data = {
                "study_uid": metadata.get("StudyInstanceUID", ""),
                "series_uid": metadata.get("SeriesInstanceUID", ""),
                "path_to_study": results.get("organized_path", ""),
                "processing_status": russian_status,
                "probability_of_pathology": results.get("probability_of_pathology", 0.0),
                "pathology": results.get("pathology", 0),
                "most_dangerous_pathology_type": results.get("most_dangerous_pathology_type", ""),
                "pathology_localization_coords": json.dumps(
                    results.get("pathology_localization_coords")) if results.get(
                    "pathology_localization_coords") else None,
                "heatmap_path": results.get("heatmap_path", ""),
                "heatmap_format": results.get("heatmap_format", ""),
                "heatmap_metadata": json.dumps(heatmap_metadata_data),
                "time_of_processing": results.get("processing_time", 0.0),
                "total_instances": results.get("total_instances", 0),
                "series_count": results.get("series_count", 0),
                "ready_for_inference": results.get("ready_for_inference", False),
                "inference_completed": results.get("inference_completed", False),
                "needs_verification": results.get("needs_review", False),  # ✅ Правильное имя поля!
                "verification_results": json.dumps(results.get("verification_results")) if results.get(
                    "verification_results") else None,
                "verification_score": results.get("verification_score"),
                "id": study_id
            }

            session.execute(
                text("""
                                UPDATE studies SET 
                                study_uid = :study_uid,
                                series_uid = :series_uid, 
                                path_to_study = :path_to_study,
                                processing_status = :processing_status,
                                probability_of_pathology = :probability_of_pathology,
                                pathology = :pathology,
                                most_dangerous_pathology_type = :most_dangerous_pathology_type,
                                pathology_localization_coords = :pathology_localization_coords,
                                heatmap_path = :heatmap_path,
                                heatmap_format = :heatmap_format,
                                heatmap_metadata = :heatmap_metadata,
                                time_of_processing = :time_of_processing,
                                total_instances = :total_instances,
                                series_count = :series_count,
                                ready_for_inference = :ready_for_inference,
                                inference_completed = :inference_completed,
                                needs_verification = :needs_verification,
                                verification_results = :verification_results,
                                verification_score = :verification_score,
                                updated_at = NOW()
                                WHERE id = :id
                            """),
                update_data
            )
            session.commit()
            logger.info(f"Успешно обновлены результаты исследования {study_id}, статус: {russian_status}")
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка обновления результатов исследования {study_id}: {e}")
            raise e