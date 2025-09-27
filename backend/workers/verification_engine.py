import numpy as np
from scipy import ndimage
import cv2
import json
from pathlib import Path

class VerificationEngine:
    def validate_normal_prediction(self, heatmap_data: dict, study_id: int) -> dict:
        """
        Проверяет предсказание «норма» на достоверность
        Адаптировано для 3D heatmap от DS
        """
        # Получаем 3D heatmap из данных DS
        error_map_3d = np.array(heatmap_data.get("error_map_3d", []))
        
        if error_map_3d.size == 0:
            return self._error_response("Heatmap данные отсутствуют")

        # Выбираем наиболее информативный срез (с максимальной ошибкой)
        slice_index = heatmap_data.get("max_error_slice_index", 0)
        heatmap_2d = error_map_3d[:, :, slice_index]

        validation_results = {
            "достоверно": True,
            "итоговый_коэффициент": 1.0,
            "предупреждения": [],
            "детали": {},
            "уровень_риска": "низкий",
            "проверенный_срез": slice_index,
            "форма_heatmap": heatmap_2d.shape
        }

        # Запускаем проверки
        checks = [
            self._check_edge_artifacts(heatmap_2d),
            self._check_attention_chaos(heatmap_2d),
            self._check_suspicious_focus_patterns(heatmap_2d),
            self._check_heatmap_quality(heatmap_2d)
        ]

        # Агрегируем результаты
        confidence_multiplier = 1.0
        risk_factors = []

        for check in checks:
            if not check["пройдено"]:
                validation_results["предупреждения"].append(check["замечание"])
                risk_factors.append(check["уровень_риска"])

            confidence_multiplier *= check["множитель_доверия"]
            validation_results["детали"][check["название_проверки"]] = check

        validation_results["итоговый_коэффициент"] = confidence_multiplier
        validation_results["достоверно"] = confidence_multiplier > 0.6
        validation_results["уровень_риска"] = self._calculate_overall_risk(risk_factors)

        # Сохраняем результаты верификации
        self._save_verification_results(validation_results, study_id)

        return validation_results

    def _check_edge_artifacts(self, heatmap: np.ndarray) -> dict:
        """Проверка: модель смотрит на края снимка, а не на лёгкие"""
        h, w = heatmap.shape
        border_width = max(10, min(h, w) // 25)

        edge_mask = np.zeros_like(heatmap, dtype=bool)
        edge_mask[:border_width, :] = True
        edge_mask[-border_width:, :] = True
        edge_mask[:, :border_width] = True
        edge_mask[:, -border_width:] = True

        corner_size = border_width * 2
        corners_attention = np.mean([
            np.mean(heatmap[:corner_size, :corner_size]),
            np.mean(heatmap[:corner_size, -corner_size:]),
            np.mean(heatmap[-corner_size:, :corner_size]),
            np.mean(heatmap[-corner_size:, -corner_size:])
        ])

        center_mask = ~edge_mask
        edge_attention = np.mean(heatmap[edge_mask])
        center_attention = np.mean(heatmap[center_mask])

        if edge_attention > center_attention * 1.4:
            return {
                "пройдено": False,
                "множитель_доверия": 0.3,
                "уровень_риска": "высокий",
                "замечание": "Модель уделяет слишком много внимания краям снимка (вероятны артефакты)",
                "название_проверки": "краевые_артефакты",
                "детали": f"Края: {edge_attention:.3f}, Центр: {center_attention:.3f}"
            }

        if corners_attention > 0.4:
            return {
                "пройдено": False,
                "множитель_доверия": 0.4,
                "уровень_риска": "высокий",
                "замечание": "Сильный фокус модели на углах изображения (ошибки позиционирования)",
                "название_проверки": "краевые_артефакты",
                "детали": f"Внимание по углам: {corners_attention:.3f}"
            }

        return {
            "пройдено": True,
            "множитель_доверия": 1.0,
            "уровень_риска": "низкий",
            "название_проверки": "краевые_артефакты"
        }

    def _check_attention_chaos(self, heatmap: np.ndarray) -> dict:
        """Проверка: внимание модели хаотично или слишком «рваное»"""
        thresholds = [0.3, 0.5, 0.7, 0.9]
        region_counts = []

        for t in thresholds:
            binary_map = heatmap > t
            _, num_regions = ndimage.label(binary_map)
            region_counts.append(num_regions)

        if region_counts[-1] > 8:
            return {
                "пройдено": False,
                "множитель_доверия": 0.4,
                "уровень_риска": "средний",
                "замечание": f"Слишком хаотичное распределение внимания ({region_counts[-1]} областей с высокой уверенностью)",
                "название_проверки": "хаос_внимания"
            }

        attention_std = np.std(heatmap)
        attention_mean = np.mean(heatmap)
        spikiness_ratio = attention_std / (attention_mean + 1e-8)

        if spikiness_ratio > 3.0:
            return {
                "пройдено": False,
                "множитель_доверия": 0.5,
                "уровень_риска": "средний",
                "замечание": f"Слишком резкие скачки внимания (коэф.: {spikiness_ratio:.2f})",
                "название_проверки": "хаос_внимания"
            }

        return {
            "пройдено": True,
            "множитель_доверия": 1.0,
            "уровень_риска": "низкий",
            "название_проверки": "хаос_внимания"
        }

    def _check_suspicious_focus_patterns(self, heatmap: np.ndarray) -> dict:
        """Проверка: подозрительные паттерны внимания"""
        h, w = heatmap.shape
        horizontal_variance = np.var(np.mean(heatmap, axis=1))
        vertical_variance = np.var(np.mean(heatmap, axis=0))

        if horizontal_variance < 0.001 or vertical_variance < 0.001:
            return {
                "пройдено": False,
                "множитель_доверия": 0.4,
                "уровень_риска": "высокий",
                "замечание": "Модель следует за линейными артефактами (полосы сканирования)",
                "название_проверки": "подозрительные_паттерны"
            }

        center_region = heatmap[h//4:3*h//4, w//4:3*w//4]
        edge_region_mask = np.ones_like(heatmap, dtype=bool)
        edge_region_mask[h//4:3*h//4, w//4:3*w//4] = False

        center_attention = np.mean(center_region)
        edge_attention = np.mean(heatmap[edge_region_mask])

        if edge_attention > center_attention * 2.5 and center_attention < 0.1:
            return {
                "пройдено": False,
                "множитель_доверия": 0.3,
                "уровень_риска": "высокий",
                "замечание": "Подозрительный паттерн: пустой центр и активные края (модель игнорирует лёгкие)",
                "название_проверки": "подозрительные_паттерны"
            }

        left_half = heatmap[:, :w//2]
        right_half = heatmap[:, w//2:]
        asymmetry_ratio = np.mean(left_half) / (np.mean(right_half) + 1e-8)

        if asymmetry_ratio > 5 or asymmetry_ratio < 0.2:
            return {
                "пройдено": False,
                "множитель_доверия": 0.6,
                "уровень_риска": "средний",
                "замечание": f"Сильная асимметрия между левым и правым лёгким (коэф.: {asymmetry_ratio:.2f})",
                "название_проверки": "подозрительные_паттерны"
            }

        return {
            "пройдено": True,
            "множитель_доверия": 1.0,
            "уровень_риска": "низкий",
            "название_проверки": "подозрительные_паттерны"
        }

    def _check_heatmap_quality(self, heatmap: np.ndarray) -> dict:
        """Проверка: карта внимания пустая или пересвеченная"""
        non_zero_ratio = np.sum(heatmap > 0.05) / heatmap.size
        if non_zero_ratio < 0.01:
            return {
                "пройдено": False,
                "множитель_доверия": 0.3,
                "уровень_риска": "высокий",
                "замечание": "Модель почти не анализировала изображение",
                "название_проверки": "качество_heatmap"
            }

        high_attention_ratio = np.sum(heatmap > 0.95) / heatmap.size
        if high_attention_ratio > 0.5:
            return {
                "пройдено": False,
                "множитель_доверия": 0.5,
                "уровень_риска": "средний",
                "замечание": "Модель выделила слишком большую часть изображения (нет фокуса)",
                "название_проверки": "качество_heatmap"
            }

        return {
            "пройдено": True,
            "множитель_доверия": 1.0,
            "уровень_риска": "низкий",
            "название_проверки": "качество_heatmap"
        }

    def _calculate_overall_risk(self, risk_factors: list) -> str:
        """Финальная оценка уровня риска"""
        if not risk_factors:
            return "низкий"

        high_risk_count = risk_factors.count("высокий")
        medium_risk_count = risk_factors.count("средний")

        if high_risk_count > 0:
            return "высокий"
        elif medium_risk_count > 1:
            return "высокий"
        elif medium_risk_count > 0:
            return "средний"
        else:
            return "низкий"

    def _save_verification_results(self, results: dict, study_id: int):
        """Сохраняет результаты верификации в файл"""
        try:
            verification_dir = Path("/app/processed_studies") / f"study_{study_id}" / "verification"
            verification_dir.mkdir(parents=True, exist_ok=True)
            
            with open(verification_dir / "verification_results.json", "w") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Ошибка сохранения результатов верификации: {e}")

    def _error_response(self, message: str) -> dict:
        """Возвращает ответ об ошибке"""
        return {
            "достоверно": False,
            "итоговый_коэффициент": 0.0,
            "предупреждения": [message],
            "детали": {},
            "уровень_риска": "высокий",
            "ошибка": True
        }

# Глобальный инстанс
verification_engine = VerificationEngine()