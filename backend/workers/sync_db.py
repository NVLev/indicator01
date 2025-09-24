"""Синхронные операции с БД для Celery задач"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

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
            update_data = {
                "study_uid": results.get("study_metadata", {}).get("StudyInstanceUID", ""),
                "series_uid": results.get("study_metadata", {}).get("SeriesInstanceUID", ""),
                "path_to_study": results.get("organized_path", ""),
                "processing_status": russian_status,
                "time_of_processing": results.get("processing_time"),
                "total_instances": results.get("total_instances", 0),
                "series_count": results.get("series_count", 0),
                "ready_for_inference": results.get("ready_for_inference", False),
                "id": study_id
            }

            session.execute(
                text("""
                    UPDATE studies SET 
                    study_uid = :study_uid,
                    series_uid = :series_uid, 
                    path_to_study = :path_to_study,
                    processing_status = :processing_status,
                    time_of_processing = :time_of_processing,
                    total_instances = :total_instances,
                    series_count = :series_count,
                    ready_for_inference = :ready_for_inference
                    WHERE id = :id
                """),
                update_data
            )
            session.commit()
        except Exception as e:
            session.rollback()
            raise e