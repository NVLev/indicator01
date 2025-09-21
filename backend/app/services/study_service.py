import os
import zipfile
import tempfile
import shutil
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import pydicom
from pydicom.errors import InvalidDicomError
import pandas as pd
from datetime import datetime
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import Depends

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


# services/study_service.py


from ..core.db_helper import db_helper
from ..core.models import Study, StudyStatus
from ..core.config import settings

logger = logging.getLogger(__name__)


thread_pool = ThreadPoolExecutor(max_workers=settings.max_workers if hasattr(settings, 'max_workers') else 4)


class DicomProcessingError(Exception):
    pass


async def process_dicom_study(
        zip_file_path: str,
        study_id: int,
        session: AsyncSession,
        output_dir: str = "processed_studies"
) -> Dict:
    """
    Распаковывает исследование DICOM из архива ZIP
    """
    start_time = time.time()
    processing_result = {
        "study_id": study_id,
        "processing_status": "Success",
        "error_message": None,
        "dicom_files": [],
        "study_metadata": {},
        "series_count": 0,
        "total_instances": 0,
        "processing_time": 0.0
    }

    try:
        # Переводим статус
        await update_study_status(study_id, StudyStatus.EXTRACTING, session)


        loop = asyncio.get_event_loop()

        # Извлекаем и обрабатываем файлы в thread pool
        processing_result = await loop.run_in_executor(
            thread_pool,
            _process_dicom_study_sync,
            zip_file_path,
            study_id,
            output_dir,
            processing_result
        )

        # Обновляем базу данных
        await update_study_results(study_id, processing_result, session)

        logger.info(f"Успешно обработано исследование {study_id}: {processing_result['total_instances']} файлов")

    except Exception as e:
        logger.error(f"Ошибка обработки исследования {study_id}: {str(e)}")
        processing_result.update({
            "processing_status": "FAILED",
            "error_message": str(e),
            "ready_for_inference": False
        })

        await update_study_status(study_id, StudyStatus.FAILED, session, str(e))

    finally:
        # Запись времени обработки
        processing_result["processing_time"] = time.time() - start_time

    return processing_result


def _process_dicom_study_sync(
        zip_file_path: str,
        study_id: int,
        output_dir: str,
        processing_result: Dict
) -> Dict:
    """
    Синхронная функция обработки DICOM - запускается в thread pool
    """
    temp_extract_dir = None

    try:
        temp_extract_dir = tempfile.mkdtemp(prefix=f"study_{study_id}_")
        logger.info(f"Processing study {study_id}, extracting to {temp_extract_dir}")

        # Извлекается архив
        dicom_files = extract_zip_archive(zip_file_path, temp_extract_dir)
        if not dicom_files:
            raise DicomProcessingError("No DICOM files found in archive")

        logger.info(f"Found {len(dicom_files)} potential DICOM files")

        # Извлекаются метаданные
        study_metadata, valid_files = parse_dicom_files(dicom_files)

        if not valid_files:
            raise DicomProcessingError("No valid DICOM files found")

        # Группируем по сериям
        series_groups = group_files_by_series(valid_files)


        organized_path = organize_dicom_files(
            series_groups,
            output_dir,
            study_metadata.get('StudyInstanceUID', f'study_{study_id}')
        )

        # Обновляются результаты обработки
        processing_result.update({
            "dicom_files": [str(f) for f in valid_files],
            "study_metadata": study_metadata,
            "series_count": len(series_groups),
            "total_instances": len(valid_files),
            "organized_path": organized_path,
            "ready_for_inference": True
        })

    except Exception as e:
        processing_result.update({
            "processing_status": "Failure",
            "error_message": str(e),
            "ready_for_inference": False
        })
        raise

    finally:
        if temp_extract_dir and os.path.exists(temp_extract_dir):
            try:
                shutil.rmtree(temp_extract_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory {temp_extract_dir}: {e}")

    return processing_result



async def update_study_status(
        study_id: int,
        status: str,
        session: AsyncSession,
        error_message: Optional[str] = None
):
    """Обновление статуса обработки в базе данных"""
    try:
        stmt = select(Study).where(Study.id == study_id)
        result = await session.execute(stmt)
        study = result.scalar_one_or_none()

        if study:
            study.processing_status = status
            if error_message:
                study.error_message = error_message
            study.updated_at = datetime.utcnow()

            await session.commit()
        else:
            logger.warning(f"Study {study_id} not found in database")

    except Exception as e:
        logger.error(f"Failed to update study status: {e}")
        await session.rollback()


async def update_study_results(
        study_id: int,
        results: Dict,
        session: AsyncSession
):
    """Обновление исследования результатом обработки"""
    try:
        stmt = select(Study).where(Study.id == study_id)
        result = await session.execute(stmt)
        study = result.scalar_one_or_none()

        if study:
            metadata = results.get('study_metadata', {})

            # Обновляются поля из спецификации
            study.study_uid = metadata.get('StudyInstanceUID', '')
            study.series_uid = metadata.get('SeriesInstanceUID', '')
            study.path_to_study = results.get('organized_path', '')
            study.processing_status = results.get('processing_status', 'Failure')
            study.time_of_processing = results.get('processing_time', 0.0)
            study.total_instances = results.get('total_instances', 0)
            study.series_count = results.get('series_count', 0)
            study.updated_at = datetime.utcnow()

            # Store metadata as JSON (if your model supports it)
            if hasattr(study, 'metadata_json'):
                study.metadata_json = metadata

            await session.commit()
            logger.info(f"Updated study {study_id} with processing results")
        else:
            logger.warning(f"Study {study_id} not found for results update")

    except Exception as e:
        logger.error(f"Failed to update study results: {e}")
        await session.rollback()


def parse_dicom_files(file_paths: List[Path]) -> Tuple[Dict, List[Path]]:
    """Метод для парсинга DICOM файлов и извлечения  метаданных"""
    study_metadata = {}
    valid_files = []
    series_info = {}

    for file_path in file_paths:
        try:
            ds = pydicom.dcmread(str(file_path), force=True)

            if not hasattr(ds, 'StudyInstanceUID'):
                logger.warning(f"File {file_path} missing StudyInstanceUID, skipping")
                continue

            # Извлекаем метаданные (из первого валидного файла)
            if not study_metadata:
                study_metadata = extract_study_metadata(ds)

            # Сбор информации о серии
            series_uid = getattr(ds, 'SeriesInstanceUID', 'unknown')
            if series_uid not in series_info:
                series_info[series_uid] = {
                    'SeriesInstanceUID': series_uid,
                    'SeriesDescription': getattr(ds, 'SeriesDescription', ''),
                    'SeriesNumber': getattr(ds, 'SeriesNumber', ''),
                    'Modality': getattr(ds, 'Modality', ''),
                    'files': []
                }

            series_info[series_uid]['files'].append(file_path)
            valid_files.append(file_path)

        except InvalidDicomError:
            logger.warning(f"File {file_path} is not a valid DICOM file")
        except Exception as e:
            logger.warning(f"Error reading {file_path}: {e}")

    study_metadata['series_info'] = series_info

    return study_metadata, valid_files


def extract_study_metadata(ds: pydicom.Dataset) -> Dict:
    """Extract relevant study metadata from DICOM dataset"""
    metadata = {}

    # необходимые поля
    metadata['StudyInstanceUID'] = getattr(ds, 'StudyInstanceUID', '')
    metadata['SeriesInstanceUID'] = getattr(ds, 'SeriesInstanceUID', '')

    # Дополнительно
    metadata['PatientID'] = getattr(ds, 'PatientID', '')
    metadata['StudyDescription'] = getattr(ds, 'StudyDescription', '')
    metadata['StudyDate'] = getattr(ds, 'StudyDate', '')
    metadata['StudyTime'] = getattr(ds, 'StudyTime', '')
    metadata['Modality'] = getattr(ds, 'Modality', '')
    metadata['Manufacturer'] = getattr(ds, 'Manufacturer', '')
    metadata['ManufacturerModelName'] = getattr(ds, 'ManufacturerModelName', '')

    # Image-specific metadata
    if hasattr(ds, 'Rows') and hasattr(ds, 'Columns'):
        metadata['ImageDimensions'] = f"{ds.Rows}x{ds.Columns}"

    if hasattr(ds, 'PixelSpacing'):
        metadata['PixelSpacing'] = list(ds.PixelSpacing)

    if hasattr(ds, 'SliceThickness'):
        metadata['SliceThickness'] = float(ds.SliceThickness)

    return metadata


def group_files_by_series(file_paths: List[Path]) -> Dict[str, List[Path]]:
    """Метод для группировки файлов DICOM по SeriesInstanceUID"""
    series_groups = {}

    for file_path in file_paths:
        try:
            ds = pydicom.dcmread(str(file_path), stop_before_pixels=True)  # Read only metadata
            series_uid = getattr(ds, 'SeriesInstanceUID', 'unknown')

            if series_uid not in series_groups:
                series_groups[series_uid] = []

            series_groups[series_uid].append(file_path)

        except Exception as e:
            logger.warning(f"Error grouping file {file_path}: {e}")

    return series_groups


def organize_dicom_files(
        series_groups: Dict[str, List[Path]],
        output_dir: str,
        study_uid: str
) -> str:
    """Метод для организации файлов DICOM в структурированую директорию"""


    study_dir = Path(output_dir) / study_uid
    study_dir.mkdir(parents=True, exist_ok=True)

    for series_uid, files in series_groups.items():

        series_dir = study_dir / series_uid
        series_dir.mkdir(exist_ok=True)


        for i, file_path in enumerate(files):
            try:
                new_filename = f"{series_uid}_{i:04d}.dcm"
                new_path = series_dir / new_filename
                shutil.copy2(file_path, new_path)

            except Exception as e:
                logger.warning(f"Failed to organize file {file_path}: {e}")

    return str(study_dir)


def extract_zip_archive(zip_path: str, extract_to: str) -> List[Path]:
    """
    Метод для распаковки архива ZIP.  Возвращает список извлеченных файлов с фильтрацией

    """
    extracted_files = []

    try:
        # Validate ZIP file
        if not zipfile.is_zipfile(zip_path):
            raise DicomProcessingError("File is not a valid ZIP archive")

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # получаем список файлов, исключая директории
            file_list = [
                f for f in zip_ref.namelist()
                if not f.endswith('/')
                   and not os.path.basename(f).startswith('.')
                   and not os.path.basename(f).startswith('__')
            ]

            if not file_list:
                raise DicomProcessingError("ZIP archive is empty")

            logger.info(f"Found {len(file_list)} files in archive, starting extraction")

            os.makedirs(extract_to, exist_ok=True)

            # Extract and filter files
            for file_name in file_list:
                try:
                    safe_filename = os.path.basename(file_name)
                    if not safe_filename or safe_filename.startswith('.'):
                        continue

                    extract_path = zip_ref.extract(file_name, extract_to)
                    extracted_path = Path(extract_path)

                    if is_likely_dicom_file(extracted_path):
                        extracted_files.append(extracted_path)
                    else:
                        # Удалить ненужные файлы для очистки места
                        os.remove(extracted_path)
                        logger.debug(f"Filtered out non-DICOM file: {file_name}")

                except Exception as e:
                    logger.warning(f"Failed to extract {file_name}: {e}")
                    continue

            logger.info(f"Successfully extracted {len(extracted_files)} potential DICOM files")

            if not extracted_files:
                raise DicomProcessingError("No DICOM files found in archive after filtering")

            return extracted_files

    except zipfile.BadZipFile:
        raise DicomProcessingError("Invalid or corrupted ZIP archive")
    except PermissionError:
        raise DicomProcessingError("Permission denied when extracting files")
    except Exception as e:
        raise DicomProcessingError(f"Failed to extract ZIP archive: {str(e)}")


def is_likely_dicom_file(file_path: Path) -> bool:
    """
    Быстрый эвристический анализ для проверки типа файла
    """
    try:
        # Наличие и размер
        if not file_path.exists():
            return False

        file_size = file_path.stat().st_size
        if file_size < 1024:
            return False

        # Расширение
        dicom_extensions = {'.dcm', '.dic', '.dicom', ''}
        if file_path.suffix.lower() not in dicom_extensions:
            return False

        # Быстрая проверка содержимого
        with open(file_path, 'rb') as f:
            header = f.read(132)

        # подпись
        if len(header) >= 132 and header[128:132] == b'DICM':
            return True

        # если стаарые файлы
        if len(header) >= 4 and header[0:4] in [b'DICM', b'MEDI', b'ACR']:
            return True

        # Все равно может быть DICOM
        return True

    except Exception:
        return False






