import sys
import os


from ML_model.Inference_with_heatmap import CTInferenceProcessor
import numpy as np
from pathlib import Path
import tempfile
import json

class MLInferenceService:
    def __init__(self, model_path: str = "/app/ML_model/best_pathology_model.keras",
                 threshold_path: str = "/app/ML_model/pathology_threshold.json"):
        self.processor = CTInferenceProcessor()
        self.model_path = model_path
        self.threshold_path = threshold_path
        
        if not self.processor.load_model(model_path, threshold_path):
            raise Exception("Не удалось загрузить ML модель")

    def analyze_study(self, organized_study_path: str, study_id: int) -> dict:
        """
        Анализ исследования с помощью ML модели
        
        Args:
            organized_study_path: Путь к организованным DICOM файлам (из вашей обработки)
            study_id: ID исследования для логирования
            
        Returns:
            Словарь с результатами ML анализа
        """
        try:
            result = self.processor.process_study_folder(organized_study_path, f"study_{study_id}")
            return self._format_result(result, study_id)
            
        except Exception as e:
            return {
                "processing_status": "failed",
                "error_message": f"ML inference error: {str(e)}",
                "probability_of_pathology": 0.0,
                "pathology": 0
            }

    def _format_result(self, ds_result: dict, study_id: int) -> dict:
        """Преобразует результат работы модели в формат пайплайна общей обработки"""
        
        # Базовые результаты
        formatted = {
            "study_id": study_id,
            "probability_of_pathology": ds_result.get("probability_of_pathology", 0.0),
            "pathology": ds_result.get("pathology_class", 0),
            "processing_status": "completed" if ds_result.get("processing_status") == "Success" else "failed",
            "ml_processing_time": ds_result.get("processing_time_seconds", 0.0),
            "reconstruction_error": ds_result.get("reconstruction_error", 0.0)
        }

        # Heatmap данные
        heatmap_data = ds_result.get("heatmap_data", {})
        if heatmap_data:
            formatted.update({
                "heatmap_statistics": heatmap_data.get("heatmap_statistics", {}),
                "max_error_slice_index": heatmap_data.get("max_error_slice_index", 0),
                "heatmap_shape": heatmap_data.get("error_map_shape", [])
            })

            heatmap_path = self._save_heatmap_data(heatmap_data, study_id)
            if heatmap_path:
                formatted["heatmap_path"] = heatmap_path
                formatted["heatmap_format"] = "npy"

        return formatted

    def _save_heatmap_data(self, heatmap_data: dict, study_id: int) -> str:
        """Сохраняет heatmap данные в файл"""
        try:
            heatmap_dir = Path("/app/processed_studies") / f"study_{study_id}" / "heatmaps"
            heatmap_dir.mkdir(parents=True, exist_ok=True)

            error_map = np.array(heatmap_data.get("error_map_3d", []))
            if error_map.size > 0:
                np.save(heatmap_dir / "error_map.npy", error_map)

            with open(heatmap_dir / "heatmap_stats.json", "w") as f:
                json.dump(heatmap_data.get("heatmap_statistics", {}), f)
                
            return str(heatmap_dir)
            
        except Exception as e:
            print(f"Ошибка сохранения heatmap: {e}")
            return ""

# Глобальный инстанс для reuse
ml_service = None

def get_ml_service():
    global ml_service
    if ml_service is None:
        ml_service = MLInferenceService()
    return ml_service