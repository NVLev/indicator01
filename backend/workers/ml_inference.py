import os
import requests
import numpy as np
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class MLInferenceService:
    """
    Клиент для общения с внешним ML-сервисом по HTTP.
    Сохраняет структуру методов как в старой реализации.
    """

    def __init__(self, service_url: str = None):
        # URL сервиса ML (имя контейнера из docker-compose.yml)
        self.service_url = service_url or os.getenv("ML_SERVICE_URL", "http://ml_service:8501")
        self.processed_dir = os.getenv("PROCESSED_DIR", "/app/processed_studies")

    def analyze_study(self, organized_study_path: str, study_id: int) -> dict:
        """
        Отправка исследования на ML-сервис для анализа и постобработка результата.

        Args:
            organized_study_path: путь к папке с организованными DICOM файлами
            study_id: ID исследования

        Returns:
            dict: результат работы ML сервиса (с форматированием)
        """
        study_path = Path(organized_study_path)

        if study_path.is_absolute():
            final_path = study_path
        else:
            # Если путь относительный, проверяем не начинается ли он уже с processed_studies
            if organized_study_path.startswith("processed_studies/"):
                # Убираем лишнюю часть пути
                relative_path = organized_study_path.replace("processed_studies/", "", 1)
                final_path = Path(self.processed_dir) / relative_path
            else:
                final_path = Path(self.processed_dir) / organized_study_path

            # Убедимся, что путь существует
        if not final_path.exists():
            logger.error(f"Путь к исследованию не существует: {final_path}")
            logger.error(f"Исходный путь: {organized_study_path}")
            logger.error(f"Базовая директория: {self.processed_dir}")

            # Попробуем найти файлы вручную
            try:
                possible_paths = list(Path(self.processed_dir).rglob("*"))
                logger.info(f"🔍 Доступные пути в {self.processed_dir}: {[str(p) for p in possible_paths[:10]]}")
            except Exception as e:
                logger.error(f"Не удалось просканировать директорию: {e}")
            return {
                "processing_status": "failed",
                "error_message": f"Study path not found: {study_path}",
                "probability_of_pathology": 0.0,
                "pathology": 0,
            }
        payload = {
            "study_path": organized_study_path,
            "study_id": study_id,
        }

        try:
            response = requests.post(
                f"{self.service_url}/predict",
                json=payload,
                timeout=60 * 8,  # до 8 минут
            )
            response.raise_for_status()
            raw_result = response.json()
            return self._format_result(raw_result, study_id)

        except requests.RequestException as e:
            return {
                "processing_status": "failed",
                "error_message": f"ML service request error: {str(e)}",
                "probability_of_pathology": 0.0,
                "pathology": 0,
            }

    def _format_result(self, ds_result: dict, study_id: int) -> dict:
        """Преобразует результат работы модели в формат пайплайна общей обработки"""

        formatted = {
            "study_id": study_id,
            "probability_of_pathology": ds_result.get("probability_of_pathology", 0.0),
            "pathology": ds_result.get("pathology_class", 0),
            "processing_status": "completed" if ds_result.get("processing_status") == "Success" else "failed",
            "ml_processing_time": ds_result.get("processing_time_seconds", 0.0),
            "reconstruction_error": ds_result.get("reconstruction_error", 0.0),
        }

        # Heatmap данные - ПЕРЕДАЕМ ВСЁ СОДЕРЖИМОЕ heatmap_data
        heatmap_data = ds_result.get("heatmap_data", {})
        if heatmap_data:
            # Сохраняем все данные из heatmap_data
            formatted.update({
                "heatmap_statistics": heatmap_data.get("heatmap_statistics", {}),
                "max_error_slice_index": heatmap_data.get("max_error_slice_index", 0),
                "heatmap_shape": heatmap_data.get("error_map_shape", []),
            })

            # Сохраняем ВСЕ heatmap_data для передачи в Celery
            formatted["heatmap_data"] = heatmap_data

            # Сохраняем heatmap файлы
            heatmap_path = self._save_heatmap_data(heatmap_data, study_id)
            if heatmap_path:
                formatted["heatmap_path"] = heatmap_path
                formatted["heatmap_format"] = "npy"

        return formatted

    def _save_heatmap_data(self, heatmap_data: dict, study_id: int) -> str:
        """Сохраняет heatmap данные в файл включая PNG визуализацию"""
        try:
            heatmap_dir = Path("/app/processed_studies") / f"study_{study_id}" / "heatmaps"
            heatmap_dir.mkdir(parents=True, exist_ok=True)

            # Сохраняем error_map если есть как numpy array
            error_map_3d = heatmap_data.get("error_map_3d")
            if error_map_3d:
                error_map_array = np.array(error_map_3d)
                np.save(heatmap_dir / "error_map.npy", error_map_array)
                logger.info(f"✅ Сохранен error_map.npy с формой {error_map_array.shape}")

            # Сохраняем PNG визуализацию если есть
            visualization_png = heatmap_data.get("visualization_png")
            if visualization_png:
                try:
                    import base64
                    png_data = base64.b64decode(visualization_png)
                    with open(heatmap_dir / "heatmap_visualization.png", "wb") as f:
                        f.write(png_data)
                    logger.info("✅ Сохранена PNG визуализация heatmap")
                except Exception as e:
                    logger.warning(f"Не удалось сохранить PNG: {e}")

            # Сохраняем статистику
            stats = heatmap_data.get("heatmap_statistics", {})
            with open(heatmap_dir / "heatmap_stats.json", "w") as f:
                json.dump({
                    "statistics": stats,
                    "max_error_slice_index": heatmap_data.get("max_error_slice_index", 0),
                    "shape": heatmap_data.get("error_map_shape", [])
                }, f, indent=2)

            logger.info(f"✅ Heatmap данные сохранены в {heatmap_dir}")
            return str(heatmap_dir)

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения heatmap: {e}")
            return ""


# Глобальный инстанс (для reuse)
ml_service = None


def get_ml_service() -> MLInferenceService:
    global ml_service
    if ml_service is None:
        ml_service = MLInferenceService()
    return ml_service
