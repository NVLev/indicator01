# services/study_service.py
from ..core.models import StudyStatus


class StudyStatusManager:
    """Менеджер для работы со статусами исследований"""

    # Словарь для маппинга статусов на понятные описания
    STATUS_DESCRIPTIONS = {
        StudyStatus.UPLOADED: "Исследование загружено и ожидает обработки",
        StudyStatus.EXTRACTING: "Идет распаковка архива с DICOM-файлами",
        StudyStatus.VALIDATING: "Проверка целостности и валидности DICOM-файлов",
        StudyStatus.PROCESSING_ML: "ИИ анализирует исследование на наличие патологий",
        StudyStatus.COMPLETED: "Обработка завершена успешно",
        StudyStatus.FAILED: "Произошла ошибка при обработке",
        StudyStatus.NEEDS_REVIEW: "Требуется проверка врачом (низкая достоверность ИИ)",
    }


    @classmethod
    def get_status_description(cls, status: StudyStatus) -> str:
        """Получить человекочитаемое описание статуса"""
        return cls.STATUS_DESCRIPTIONS.get(status, "Неизвестный статус")

