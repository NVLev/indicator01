# Структура проекта

```bash
indicator01/
├── backend/                      # Основная папка бэкенда
│   ├── alembic.ini          
│   ├── alembic/                  # Папка с миграциями
│   │   ├── versions/
│   │   ├── env.py
│   │   └── script.py.mako
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
│   └──requirements_backend.txt  # Зависимости бэкенда
│  
├── ML_model/               # Код для использования обученных моделей
│   ├── heatmap.py    
│   ├── Inference.py 
│   ├── ML_model.py       
│   └── Inference_with_heatmap.py  
│
├── inference/                   
│
├── Dockerfile                # Контейнеризация бэкенда
├── docker-compose.yml            # Оркестрация сервисов
├── requirements.txt              # Общие зависимости (training + inference)
└── README.md                     # Документация
```
# Быстрый старт

## 1. Настройка окружения
```bash
cp .env.template .env
```

## 2. Запуск всей системы (включая миграции)

### Запуск БД и выполнение миграций
docker compose --profile migrations up -d

### Или пошагово:
docker compose up pg -d
docker compose --profile migrations run --rm alembic alembic upgrade head
docker compose up -d

## 3. Проверка работы

- API документация: http://localhost:8000/docs

- Adminer (БД): http://localhost:8080

- Flower (мониторинг Celery): http://localhost:5555

# Архитектура сервисов


Или более компактный вариант, если нужно сэкономить место:

```markdown

| Сервис         | Порт | Назначение  | Профиль |
|----------------|------|-------------|---------|
| **backend**    | 8000 | FastAPI API |    -    |
| **pg**         | 5432 | База данных |    -    |
| **redis**      | 6380 | Кэш & Celery|    -    |
| **ml_service** | 8501 | ИИ модель   |    -    |
| **alembic**    |  -   | Миграции БД | `migrations` |
| **flower**     | 5555 | Мониторинг  | `monitoring` |
| **adminer**    | 8080 | Веб-БД      |    -    |

**Доступ:** http://localhost:8000/docs • http://localhost:8080 • http://localhost:5555
```