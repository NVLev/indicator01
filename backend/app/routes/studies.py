import logging
import os
import tempfile
from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from workers.tasks import process_complete_study_task

from ..core.db_helper import db_helper
from ..core.models import Study, StudyStatus, User
from ..core.schemas import ExcelReportRequest, StudyListResponse, StudyResponse
from ..services.security import get_current_user
from ..services.study_service import StudyService, create_excel_report

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/studies", tags=["Исследования"])
demo_router = APIRouter(prefix="/demo", tags=["Демо"])


@router.post("/upload", response_model=StudyResponse, summary="Загрузить исследование")
async def upload_study(
    file: UploadFile = File(..., description="ZIP-архив с DICOM файлами"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_getter),
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
        if not file.filename or not file.filename.lower().endswith(".zip"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Поддерживаются только ZIP-архивы",
            )
        # Создаем директорию для загруженных файлов
        upload_dir = Path("/app/backend/uploads") / str(current_user.id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Сохраняем файл
        file_path = upload_dir / file.filename
        content = await file.read()

        with open(file_path, "wb") as buffer:
            buffer.write(content)
        if not file_path.exists() or file_path.stat().st_size == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось сохранить файл на сервер",
            )
        # Создаем запись в БД
        study = await StudyService.create_study(
            user_id=current_user.id,  # noqa: PyCharm ложное срабатывание
            filename=file.filename,
            file_path=str(file_path),
            session=session,
        )

        # Запускаем обработку в Celery
        task_result = process_complete_study_task.delay(
            zip_file_path=str(file_path), study_id=study.id
        )

        # Логируем успешное сохранение
        logger.info(
            f"Файл успешно сохранен: {file_path}, размер: {file_path.stat().st_size} байт"
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
            "updated_at": study.updated_at,
            "heatmap_visualization_url": f"/studies/{study.id}/heatmap",
        }
        return StudyResponse(**study_data)

    except Exception as e:
        # Удаляем файл в случае ошибки
        if "file_path" in locals() and file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка загрузки файла: {str(e)}",
        )


@router.get("/", response_model=StudyListResponse, summary="Список исследований")
async def get_user_studies(
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_getter),
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
        user_id=current_user.id,  # noqa: PyCharm ложное срабатывание
        session=session,
        limit=per_page,
        offset=offset,
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
        total_pages=(total + per_page - 1) // per_page,
    )


@router.get(
    "/{study_id}", response_model=StudyResponse, summary="Информация об исследовании"
)
async def get_study(
    study_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_getter),
):
    """
    Получить детальную информацию о конкретном исследовании
    """
    study = await StudyService.get_study(
        study_id, current_user.id, session
    )  # noqa: PyCharm ложное срабатывание

    if not study:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Исследование не найдено"
        )
    study_response = StudyResponse.model_validate(study)
    study_dict = study_response.model_dump()
    study_dict["heatmap_visualization_url"] = f"/studies/{study_id}/heatmap"
    return study_dict


@router.get("/{study_id}/progress", summary="Прогресс обработки")
async def get_task_progress(
    study_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_getter),
):
    """
    Получить детальный прогресс выполнения задачи обработки

    Возвращает текущий статус, процент выполнения и сообщение о состоянии
    """
    study = await StudyService.get_study(
        study_id, current_user.id, session
    )  # noqa: PyCharm ложное срабатывание

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
    task_id = getattr(study, "task_id", None)
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
            "message": f"Статус: {status_enum.value}",
            "estimated_time": "До 10 минут",
        }

    # Получаем статус задачи из Celery
    from workers.tasks import celery_app

    task_result = celery_app.AsyncResult(study.task_id)

    response = {
        "study_id": study.id,
        "celery_task_id": study.task_id,
        "celery_state": task_result.state,
    }

    if task_result.state == "PENDING":
        response.update(
            {
                "status": "ожидание",
                "progress": 0,
                "message": "Задача в очереди на выполнение",
            }
        )
    elif task_result.state == "PROGRESS":
        progress_info = task_result.info or {}
        response.update(
            {
                "status": "выполняется",
                "progress": progress_info.get("current", 0),
                "total": progress_info.get("total", 100),
                "message": progress_info.get("status", "Обработка..."),
                "elapsed_time": progress_info.get("elapsed_time", 0),
                "time_remaining": progress_info.get("time_remaining", 600),
            }
        )
    elif task_result.state == "SUCCESS":
        response.update(
            {
                "status": "завершено",
                "progress": 100,
                "message": "Обработка завершена успешно",
                "result_available": True,
            }
        )
    elif task_result.state == "FAILURE":
        response.update(
            {
                "status": "ошибка",
                "progress": 0,
                "message": f"Ошибка обработки: {str(task_result.info)}",
                "error": True,
            }
        )
    else:
        response.update(
            {
                "status": task_result.state,
                "progress": 0,
                "message": f"Неизвестное состояние: {task_result.state}",
            }
        )

    return response


@router.post("/{study_id}/retry", summary="Повторить обработку")
async def retry_study_processing(
    study_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_getter),
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
            detail="Можно повторить только неудавшиеся обработки",
        )

    try:
        # Сбрасываем статус
        study.processing_status = StudyStatus.UPLOADED
        study.error_message = None

        # Запускаем новую задачу
        task_result = process_complete_study_task.delay(
            zip_file_path=study.file_path, study_id=study.id
        )

        study.task_id = task_result.id
        await session.commit()

        return {
            "message": "Обработка перезапущена",
            "task_id": task_result.id,
            "estimated_time": "До 10 минут",
        }

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка перезапуска: {str(e)}",
        )


@router.get("/{study_id}/export", summary="Экспорт в Excel")
async def export_study_excel(
    study_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_getter),
):
    """
    Экспорт результатов исследования в Excel файл согласно ТЗ

    Формат соответствует требованиям технического задания
    """
    study = await StudyService.get_study(study_id, current_user.id, session)

    if not study:
        raise HTTPException(status_code=404, detail="Исследование не найдено")

    allowed_statuses = [StudyStatus.COMPLETED, StudyStatus.NEEDS_REVIEW]
    if study.processing_status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Исследование еще не обработано",
        )

    if not study.inference_completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ML анализ исследования не завершен",
        )
    try:
        # ИСПРАВЛЕНИЕ: Используем актуальные метаданные из metadata_json
        metadata_json = getattr(study, "metadata_json", {}) or {}
        study_structure = metadata_json.get("study_structure", {})

        # Берем UID из обновленной структуры или fallback на старые поля
        study_uid = metadata_json.get("primary_study_uid") or study.study_uid or ""
        series_uid = metadata_json.get("primary_series_uid") or study.series_uid or ""

        # Получаем информацию о структуре исследования
        total_studies = study_structure.get("total_studies", 1)
        total_series = study_structure.get("total_series", 1)
        is_multi_study = study_structure.get("is_multi_study", False)
        is_multi_series = study_structure.get("is_multi_series", False)

        # Подготавливаем данные для отчета с ПРАВИЛЬНЫМИ UID
        study_data = {
            "organized_path": study.path_to_study or "",
            "study_metadata": {
                "StudyInstanceUID": study.study_uid or "",
                "SeriesInstanceUID": study.series_uid or "",
            },
            "processing_status": (
                "Success"
                if study.processing_status in ["completed", "обработано"]
                else "Needs Review"
            ),
            "processing_time": study.time_of_processing or 0.0,
            "probability_of_pathology": study.probability_of_pathology or 0.0,
            "pathology": study.pathology or 0,
            "most_dangerous_pathology_type": study.most_dangerous_pathology_type or "",
            "pathology_localization_coords": study.pathology_localization_coords
            or None,
        }

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            excel_path = tmp_file.name

        create_excel_report([study_data], excel_path)

        filename = f"study_{study_id}_report.xlsx"

        # Логируем для отладки
        logger.info(f"📊 Создан Excel отчет для исследования {study_id}")
        logger.info(f"  Study UID: {study_uid}")
        logger.info(f"  Series UID: {series_uid}")
        logger.info(f"  Структура: {total_studies} studies, {total_series} series")
        logger.info(
            f"  Мульти-исследование: {is_multi_study}, Мульти-серии: {is_multi_series}"
        )

        return FileResponse(
            excel_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        logger.error(
            f"❌ Ошибка создания Excel отчета для исследования {study_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания отчета: {str(e)}",
        )
    finally:
        # Файл будет удален после отправки благодаря delete=False
        pass


@router.post(
    "/upload/bulk",
    response_model=List[StudyResponse],
    summary="Массовая загрузка исследований",
)
async def upload_studies_bulk(
    files: List[UploadFile] = File(
        ..., description="Список ZIP-архивов с DICOM файлами"
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_getter),
):
    """
    Массовая загрузка нескольких ZIP-архивов одновременно

    - Максимум 20 файлов за раз
    - Каждый файл до 500MB
    - Формат: ZIP архивы с DICOM файлами
    - Обработка каждого занимает до 10 минут
    """

    if len(files) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Максимум 20 файлов за раз. Текущее количество: {len(files)}",
        )

    # Валидация расширений
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".zip"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Файл {file.filename} не является ZIP-архивом",
            )

    upload_dir = Path("/app/backend/uploads") / str(current_user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    uploaded_studies: list[StudyResponse] = []
    failed_uploads: list[dict] = []

    for file in files:
        file_path = upload_dir / file.filename
        try:
            # Потоковая запись вместо чтения в память
            with open(file_path, "wb") as buffer:
                while chunk := await file.read(1024 * 1024):  # читаем по 1Мб
                    buffer.write(chunk)
            await file.close()

            if not file_path.exists() or file_path.stat().st_size == 0:
                raise ValueError("Не удалось сохранить файл на сервер")

            # Создаём запись в БД
            study = await StudyService.create_study(
                user_id=current_user.id,
                filename=file.filename,
                file_path=str(file_path),
                session=session,
            )

            # Запускаем задачу в Celery
            task_result = process_complete_study_task.delay(
                zip_file_path=str(file_path), study_id=study.id
            )

            study.task_id = task_result.id
            await session.commit()
            await session.refresh(study)

            # Формируем DTO
            study_response = StudyResponse.model_validate(study)
            study_dict = study_response.model_dump()
            study_dict["heatmap_visualization_url"] = f"/studies/{study.id}/heatmap"

            uploaded_studies.append(StudyResponse(**study_dict))
            logger.info(f"Файл {file.filename} успешно загружен (study_id={study.id})")

        except Exception as e:
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as cleanup_err:
                    logger.warning(
                        f"Не удалось удалить файл {file_path}: {cleanup_err}"
                    )
            failed_uploads.append({"filename": file.filename, "error": str(e)})
            logger.error(f"Ошибка загрузки {file.filename}: {e}")

    if not uploaded_studies and failed_uploads:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Не удалось загрузить ни одного файла",
                "failed_files": failed_uploads,
            },
        )

    if failed_uploads:
        logger.warning(
            f"Загружено {len(uploaded_studies)} из {len(files)} файлов. Ошибки: {failed_uploads}"
        )

    return uploaded_studies


@router.get(
    "/{study_id}/heatmap",
    summary="Получить heatmap визуализацию",
    response_class=FileResponse,
)
async def get_heatmap_visualization(
    study_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_getter),
):
    """
    Получить PNG визуализацию heatmap для исследования

    - Возвращает PNG изображение с визуализацией heatmap
    - Показывает области, которые модель считает аномальными
    - Используется для объяснения решения ИИ врачу
    """
    study = await StudyService.get_study(study_id, current_user.id, session)

    if not study:
        raise HTTPException(status_code=404, detail="Исследование не найдено")

    # Проверяем, есть ли heatmap путь
    if not study.heatmap_path:
        raise HTTPException(
            status_code=404, detail="Heatmap данные не найдены для этого исследования"
        )

    heatmap_path = Path(study.heatmap_path) / "heatmap_visualization.png"

    if not heatmap_path.exists():
        # Пробуем альтернативные пути
        alternative_paths = [
            Path(study.heatmap_path) / "heatmap_visualization.png",
            Path("/app/processed_studies")
            / f"study_{study_id}"
            / "heatmaps"
            / "heatmap_visualization.png",
            Path(study.path_to_study) / "heatmaps" / "heatmap_visualization.png",
        ]

        for alt_path in alternative_paths:
            if alt_path.exists():
                heatmap_path = alt_path
                break
        else:
            raise HTTPException(
                status_code=404, detail="Визуализация heatmap не найдена"
            )

    return FileResponse(
        heatmap_path, filename=f"heatmap_study_{study_id}.png", media_type="image/png"
    )


@router.delete("/{study_id}", summary="Удалить исследование")
async def delete_study(
    study_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_getter),
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
            detail=f"Ошибка удаления: {str(e)}",
        )
