from typing import Optional, Dict, Any


class DemoService:
    """Сервис для работы с демо-режимом"""

    _demo_tokens: Optional[Dict] = None
    _demo_user = None

    @classmethod
    def set_demo_data(cls, user: Any, tokens: Dict):
        """Устанавливает демо-данные"""
        cls._demo_user = user
        cls._demo_tokens = tokens

    @classmethod
    def get_auth_headers(cls) -> Dict[str, str]:
        """Возвращает headers с JWT токеном для API запросов"""
        if cls._demo_tokens and cls._demo_tokens.get('access_token'):
            return {
                "Authorization": f"Bearer {cls._demo_tokens['access_token']}",
                "Content-Type": "application/json"
            }
        return {}

    @classmethod
    def is_ready(cls) -> bool:
        """Проверяет, готов ли демо-режим"""
        return cls._demo_tokens is not None and cls._demo_user is not None

    @classmethod
    def get_demo_user(cls):
        """Возвращает демо-пользователя"""
        return cls._demo_user

    @classmethod
    def get_demo_tokens(cls):
        """Возвращает демо-токены"""
        return cls._demo_tokens