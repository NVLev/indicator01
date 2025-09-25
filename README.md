# Структура проекта

```bash
indicator01/
├── backend/                      # Основная папка бэкенда
│   ├── app/                      # Исходники сервисного приложения
│   │   ├── main.py               # Точка входа (FastAPI/Flask сервис)
│   │   ├── routes/               # HTTP-эндпоинты
│   │   │   ├── auth.py           # Ручки для авторизации
│   │   │   └── studies.py         # Ручки для приёма и передачи данных
│   │   │
│   │   ├── services/             # Логика работы сервисов
│   │   │   ├── auth_service.py   # Функции авторизации
│   │   │   ├── study_service.py  # Функции для работы с исследованиями
│   │   │   └── security.py       # Функции для облегчения работы с авторизацией
│   │   │
│   │   ├── core/                 # Вспомогательные файлы
│   │   │   ├── models.py         # ORM-модели
│   │   │   ├── schemas.py        # Pydantic-схемы
│   │   │   ├── db_helper.py      # Настройки соединения с БД (асинхронный генератор сессий)
│   │   │   └── config.py         # Конфигурация (пути, параметры сервиса)
│   │   │
│   ├── workers/              # Фоновые задачи/воркеры
│   │   │   ├── tasks.py          # Задачи Celery
│   │   │   └── worker.py         # Настройки Celery
│   │   │
│   ├── requirements_backend.txt  # Зависимости бэкенда
│   ├── ML_model/               # Код для использования обученных моделей
│   │   │   ├── heatmap.py    
│   │   │   ├── Inference.py 
│   │   │   ├── ML_model.py       
│   │   │   └── Inference_with_heatmap.py         
│  
│   
│
├── inference/                   
│
├── Dockerfile                # Контейнеризация бэкенда
├── docker-compose.yml            # Оркестрация сервисов
├── requirements_bareaking.txt              # Общие зависимости (training + inference)
└── README.md                     # Документация
```