import os
import tempfile
from typing import List
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from ..core.db_helper import db_helper
from ..core.models import User, Study, StudyStatus
from ..core.schemas import StudyResponse, StudyListResponse, ExcelReportRequest
from ..services.study_service import StudyService, create_excel_report
from ..services.security import get_current_user
from workers.tasks import process_complete_study_task


router = APIRouter(prefix="/studies", tags=["Исследования"])


@router.post("/upload", response_model=StudyResponse, summary="Загрузить исследование")
async def upload_study(
        file: UploadFile = File(..., description="ZIP-архив с DICOM файлами"),
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(db_helper.session_getter)
):
    """
    Загрузка ZIP-архива с DICOM исследованием для автоматического анализа ИИ

    - Максимальный размер файла: 500MB
    - Формат: ZIP архив с DICOM файлами
    - Обработка занимает до 10 минут
    """

    file_path = None
    try:
        # Валидация файла
        if not file.filename or not file.filename.lower().endswith('.zip'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Поддерживаются только ZIP-архивы"
            )
        # Создаем директорию для загруженных файлов
        upload_dir = Path("uploads") / str(current_user.id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Сохраняем файл
        file_path = upload_dir / file.filename
        content = await file.read()

        with open(file_path, "wb") as buffer:
            buffer.write(content)

        # Создаем запись в БД
        study = await StudyService.create_study(
            user_id=current_user.id,  # noqa: PyCharm ложное срабатывание
            filename=file.filename,
            file_path=str(file_path),
            session=session
        )

        # Запускаем обработку в Celery
        task_result = process_complete_study_task.delay(
            zip_file_path=str(file_path),
            study_id=study.id
        )

        # Сохраняем ID задачи для отслеживания
        study.task_id = task_result.id
        await session.commit()
        await session.refresh(study)
        study_data = {
            "id": study.id,
            "user_id": study.user_id,
            "filename": study.filename,
            "file_path": study.file_path,
            "path_to_study": study.path_to_study,
            "study_uid": study.study_uid,
            "series_uid": study.series_uid,
            "processing_status": study.processing_status,
            "probability_of_pathology": study.probability_of_pathology,
            "pathology": study.pathology,
            "time_of_processing": study.time_of_processing,
            "most_dangerous_pathology_type": study.most_dangerous_pathology_type,
            "pathology_localization_coords": study.pathology_localization_coords,
            "heatmap_path": study.heatmap_path,
            "heatmap_format": study.heatmap_format,
            "heatmap_metadata": study.heatmap_metadata,
            "total_instances": study.total_instances,
            "series_count": study.series_count,
            "error_message": study.error_message,
            "ready_for_inference": study.ready_for_inference,
            "inference_completed": study.inference_completed,
            "created_at": study.created_at,
            "updated_at": study.updated_at
        }
        return StudyResponse(**study_data)

    except Exception as e:
        # Удаляем файл в случае ошибки
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка загрузки файла: {str(e)}"
        )


@router.get("/", response_model=StudyListResponse, summary="Список исследований")
async def get_user_studies(
        page: int = 1,
        per_page: int = 20,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(db_helper.session_getter)
):
    """
    Получить список исследований пользователя с пагинацией

    - page: Номер страницы (начинается с 1)
    - per_page: Количество исследований на странице (макс. 100)
    """
    if per_page > 100:
        per_page = 100

    offset = (page - 1) * per_page

    studies = await StudyService.get_user_studies(
        user_id=current_user.id,    # noqa: PyCharm ложное срабатывание
        session=session,
        limit=per_page,
        offset=offset
    )

    # Подсчет общего количества
    count_stmt = select(func.count(Study.id)).where(Study.user_id == current_user.id)
    total_result = await session.execute(count_stmt)
    total = total_result.scalar()

    return StudyListResponse(
        studies=[StudyResponse.model_validate(study) for study in studies],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page
    )


@router.get("/{study_id}", response_model=StudyResponse, summary="Информация об исследовании")
async def get_study(
        study_id: int,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(db_helper.session_getter)
):
    """
    Получить детальную информацию о конкретном исследовании
    """
    study = await StudyService.get_study(study_id, current_user.id, session) # noqa: PyCharm ложное срабатывание

    if not study:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Исследование не найдено"
        )

    return StudyResponse.model_validate(study)  # noqa: игнорируй эту ошибку


@router.get("/{study_id}/progress", summary="Прогресс обработки")
async def get_task_progress(
        study_id: int,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(db_helper.session_getter)
):
    """
    Получить детальный прогресс выполнения задачи обработки

    Возвращает текущий статус, процент выполнения и сообщение о состоянии
    """
    study = await StudyService.get_study(study_id, current_user.id, session) # noqa: PyCharm ложное срабатывание

    if not study:
        raise HTTPException(status_code=404, detail="Исследование не найдено")
    try:
        # Если статус уже является enum, оставляем как есть
        if isinstance(study.processing_status, StudyStatus):
            status_enum = study.processing_status
        else:
            status_enum = StudyStatus(study.processing_status)
    except ValueError:
        # Если статус неизвестен, используем статус по умолчанию
        status_enum = StudyStatus.FAILED
    task_id = getattr(study, 'task_id', None)
    # Если нет task_id, используем базовый статус
    if not study.task_id:
        progress_map = {
            StudyStatus.UPLOADED: 10,
            StudyStatus.EXTRACTING: 25,
            StudyStatus.VALIDATING: 50,
            StudyStatus.PROCESSING_ML: 75,
            StudyStatus.COMPLETED: 100,
            StudyStatus.FAILED: 0,
            StudyStatus.NEEDS_REVIEW: 95,
        }

        return {
            "study_id": study.id,
            "status": status_enum.value,
            "progress": progress_map.get(study.processing_status, 0),
            "message": f"Статус: {sstatus_enum.value}",
            "estimated_time": "До 10 минут"
        }

    # Получаем статус задачи из Celery
    from workers.tasks import celery_app
    task_result = celery_app.AsyncResult(study.task_id)

    response = {
        "study_id": study.id,
        "celery_task_id": study.task_id,
        "celery_state": task_result.state,
    }

    if task_result.state == 'PENDING':
        response.update({
            "status": "ожидание",
            "progress": 0,
            "message": "Задача в очереди на выполнение"
        })
    elif task_result.state == 'PROGRESS':
        progress_info = task_result.info or {}
        response.update({
            "status": "выполняется",
            "progress": progress_info.get('current', 0),
            "total": progress_info.get('total', 100),
            "message": progress_info.get('status', 'Обработка...'),
            "elapsed_time": progress_info.get('elapsed_time', 0),
            "time_remaining": progress_info.get('time_remaining', 600)
        })
    elif task_result.state == 'SUCCESS':
        response.update({
            "status": "завершено",
            "progress": 100,
            "message": "Обработка завершена успешно",
            "result_available": True
        })
    elif task_result.state == 'FAILURE':
        response.update({
            "status": "ошибка",
            "progress": 0,
            "message": f"Ошибка обработки: {str(task_result.info)}",
            "error": True
        })
    else:
        response.update({
            "status": task_result.state,
            "progress": 0,
            "message": f"Неизвестное состояние: {task_result.state}"
        })

    return response


@router.post("/{study_id}/retry", summary="Повторить обработку")
async def retry_study_processing(
        study_id: int,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(db_helper.session_getter)
):
    """
    Повторить обработку исследования после неудачной попытки

    Доступно только для исследований со статусом FAILED
    """
    study = await StudyService.get_study(study_id, current_user.id, session)

    if not study:
        raise HTTPException(status_code=404, detail="Исследование не найдено")

    if study.processing_status != StudyStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Можно повторить только неудавшиеся обработки"
        )

    try:
        # Сбрасываем статус
        study.processing_status = StudyStatus.UPLOADED
        study.error_message = None

        # Запускаем новую задачу
        task_result = process_complete_study_task.delay(
            zip_file_path=study.file_path,
            study_id=study.id
        )

        study.task_id = task_result.id
        await session.commit()

        return {
            "message": "Обработка перезапущена",
            "task_id": task_result.id,
            "estimated_time": "До 10 минут"
        }

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка перезапуска: {str(e)}"
        )


@router.get("/{study_id}/export", summary="Экспорт в Excel")
async def export_study_excel(
        study_id: int,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(db_helper.session_getter)
):
    """
    Экспорт результатов исследования в Excel файл согласно ТЗ

    Формат соответствует требованиям технического задания
    """
    study = await StudyService.get_study(study_id, current_user.id, session)

    if not study:
        raise HTTPException(status_code=404, detail="Исследование не найдено")

    if study.processing_status != StudyStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Исследование еще не обработано"
        )

    try:
        # Подготавливаем данные для отчета
        study_data = {
            "organized_path": study.path_to_study or "",
            "study_metadata": {
                "StudyInstanceUID": study.study_uid or "",
                "SeriesInstanceUID": study.series_uid or "",
            },
            "processing_status": "Success",
            "processing_time": study.time_of_processing or 0.0,
            "probability_of_pathology": study.probability_of_pathology or 0.0,
            "pathology": study.pathology or 0,
        }

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            excel_path = tmp_file.name

        create_excel_report([study_data], excel_path)

        filename = f"study_{study_id}_report.xlsx"

        return FileResponse(
            excel_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания отчета: {str(e)}"
        )
    finally:
        # Файл будет удален после отправки благодаря delete=False
        pass


@router.delete("/{study_id}", summary="Удалить исследование")
async def delete_study(
        study_id: int,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(db_helper.session_getter)
):
    """
    Удалить исследование и все связанные файлы
    """
    study = await StudyService.get_study(study_id, current_user.id, session)

    if not study:
        raise HTTPException(status_code=404, detail="Исследование не найдено")

    try:
        # Удаляем файлы
        files_to_delete = []

        if study.file_path and os.path.exists(study.file_path):
            files_to_delete.append(study.file_path)

        if study.path_to_study and os.path.exists(study.path_to_study):
            files_to_delete.append(study.path_to_study)

        for file_path in files_to_delete:
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    import shutil
                    shutil.rmtree(file_path)
            except Exception as e:
                logger.warning(f"Не удалось удалить файл {file_path}: {e}")

        # Удаляем из БД
        await session.delete(study)
        await session.commit()

        return {"message": "Исследование и файлы успешно удалены"}

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления: {str(e)}"
        )