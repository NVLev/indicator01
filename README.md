# 🩺 AI Service for Chest CT Scan Analysis

## 📋 Overview
An AI-powered service for automated analysis of chest computed tomography (CT) studies.  
The system accepts DICOM studies packaged as ZIP archives, processes them using a machine learning model, and generates detailed reports with visualizations of potential pathology regions.

A key feature of the project is the **RAG-based verification system** integrated into the backend.  
When the model classifies a study as *normal*, an additional module checks the attention map (heatmap) and flags suspicious cases — reducing the risk of false negatives.

---

## 🎯 Key Features
- 📤 Upload of studies (ZIP archives containing DICOM files)  
- ⚙️ Asynchronous processing with Celery workers  
- 🤖 AI analysis: pathology probability (normal / abnormal)  
- 🗺️ Heatmap visualization highlighting model attention regions  
- 📍 Pathology localization (coordinates in reports)  
- 📊 Excel reports (structured per technical specifications)  
- 🔑 JWT authentication  
- 🌐 Fully documented REST API  
- 🧪 Demo mode (ready-to-use backend UI for evaluation)  
- 🛡️ RAG-based verification of “normal” predictions (VerificationEngine)

---

## 📁 Supported Formats
- **Input:** ZIP archives with DICOM files (`.dcm`)  
- **Output:** Excel reports (`.xlsx`), PNG heatmaps  
- **Maximum file size:** 500 MB per archive  
- **Encoding standard:** DICOM  

---

## 🖥️ System Requirements
### Minimum
- Docker 20.10+  
- Docker Compose 2.0+  
- 8 GB RAM  
- 10 GB free disk space  

### Recommended
- 16 GB RAM  
- 50+ GB free disk space  
- NVIDIA GPU (8 GB+) for full ML model performance  

---

## 🚀 Quick Start (Recommended for testing large volumes, e.g., 200+ archives)
1. **Clone the repository:**
   ```bash
   git clone https://github.com/NVLev/indicator01
   cd indicator01
   ```

2. **Configure the environment:**
   ```bash
   cp .env.template .env
   # Edit .env as needed
   ```

3. **Build and run services:**

   #### Build images before first launch:
   ```bash
   docker compose build
   ```

   #### Start database and apply migrations:
   ```bash
   docker compose --profile migrations up -d
   ```

   **Alternatively, step-by-step:**
   ```bash
   docker compose up pg -d
   docker compose --profile migrations run --rm alembic alembic upgrade head
   docker compose up -d
   ```

4. **Check running services:**
   - Demo interface: [http://localhost:8000/demo/](http://localhost:8000/demo/)  
   - API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)  

   To monitor logs:
   ```bash
   docker compose logs -f backend
   docker compose logs -f ml_service
   docker compose logs -f celery_worker
   ```

---

## 📊 API Features
### 🔐 Authentication
- `POST /auth/register` — Register a new user  
- `POST /auth/login` — Obtain a JWT token  

### 📁 Study Management
#### Upload Studies
- `POST /studies/upload` — Upload a single study (ZIP archive)  
- `POST /studies/upload/bulk` — Upload up to 20 studies at once  

#### Retrieve Study Information
- `GET /studies/` — List user studies with pagination  
- `GET /studies/{study_id}` — Get detailed study information  
- `GET /studies/{study_id}/progress` — Check processing progress  

#### Export and Visualization
- `GET /studies/{study_id}/export` — Export results to Excel (per specifications)  
- `GET /studies/{study_id}/heatmap` — Retrieve PNG heatmap visualization  

#### Study Management
- `POST /studies/{study_id}/retry` — Retry failed study processing  
- `DELETE /studies/{study_id}` — Delete study and associated files  

---

## 🛡️ RAG Verification System
To reduce false “normal” classifications, the **VerificationEngine** module analyzes the model’s heatmap and evaluates prediction reliability.  
This is crucial for identifying borderline or ambiguous studies.

**Validation aspects include:**
- Focus on relevant anatomical areas  
- Absence of edge artifacts  
- Informative activation map distribution  
- Proper heatmap attention spread  

**Verification results:**
- ✅ `accept_normal` — prediction deemed reliable  
- ⚠️ `manual_review_recommended` — human review suggested  
- 🚨 `manual_review_required` — high probability of model error  

---

## 📁 Project Structure
```bash
indicator01/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── main.py          # Application entry point
│   │   ├── routes/          # HTTP endpoints
│   │   │   ├── auth.py
│   │   │   ├── studies.py
│   │   │   └── demo.py
│   │   ├── services/        # Business logic
│   │   │   ├── auth_service.py
│   │   │   ├── study_service.py
│   │   │   └── demo_service.py
│   │   ├── static/          # Static assets
│   │   ├── templates/       # HTML templates for demo
│   │   ├── core/            # Core modules
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   └── config.py
│   ├── workers/
│   │   └── tasks.py         # Celery tasks
│   └── requirements_backend.txt
├── front_documentation/
│   ├── api_spec.json
│   └── API_SPEC_FULL.md
├── ML_model/
│   ├── Inference.py
│   ├── heatmap.py
│   └── ML_model.py
├── docker-compose.yml
├── Dockerfile
├── Dockerfile.ml
└── .env.template
```

---

## 🧑‍💻 Authors and Credits

### Project Author
**Natalia Levant** — system architecture, backend, API design, documentation, and deployment  
GitHub: [https://github.com/NVLev](https://github.com/NVLev)

### ML Model Development
**Data Scientist — AllexShv**  
GitHub: [https://github.com/AllexShv](https://github.com/AllexShv)  
(CT analysis model design and training)

### Copyright Notice
© 2025 Natalia Levant and collaborators.  
The project is released for educational and research purposes.  
Non-commercial use is permitted with attribution.  
Commercial use requires explicit permission from the copyright holders.


# 🩺 ИИ-сервис анализа КТ исследований грудной клетки

## 📋 Краткое описание
Сервис для автоматического анализа компьютерной томографии (КТ) грудной клетки с использованием искусственного интеллекта.  
Система принимает DICOM-исследования в формате ZIP, обрабатывает их с помощью ML-модели и предоставляет детализированные отчеты с визуализацией областей патологии.

Особенность проекта — реализация **RAG-системы верификации** на бэкенде.  
Если модель классифицирует исследование как «норма», дополнительный модуль проверяет карту внимания (heatmap) и выявляет подозрительные случаи, чтобы снизить риск ложного отрицательного результата.

---

## 🎯 Основные возможности
- 📤 Загрузка исследований (ZIP архивы с DICOM)
- ⚙️ Асинхронная обработка через Celery workers
- 🤖 AI-анализ: вероятность патологии (норма/патология)
- 🗺️ Heatmap-визуализация областей, на которые «смотрела» модель
- 📍 Локализация патологий (координаты областей в отчётах)
- 📊 Excel отчёты (структура по ТЗ)
- 🔑 JWT-аутентификация
- 🌐 REST API (полностью документирован)
- 🧪 Демо-режим (готовый интерфейс для проверки без фронтенда)
- 🛡️ RAG-проверка нормальных предсказаний (VerificationEngine)

---

## 📁 Поддерживаемые форматы
- **Входные данные:** ZIP архивы с DICOM файлами (.dcm)
- **Выходные данные:** Excel отчеты (.xlsx), PNG heatmap
- **Максимальный размер:** 500 MB на архив
- **Кодировка:** DICOM стандарт

---


## Запуск локально

## 🖥️ Системные требования
### Минимальные
- Docker 20.10+
- Docker Compose 2.0+
- 8 GB RAM
- 10 GB свободного места

### Рекомендуемые
- 16 GB RAM
- 50+ GB свободного места
- NVIDIA GPU (8 GB+) при использовании полной ML-модели

## 🚀 Быстрый старт (локально, рекомендуется для проверки на больших объёмах (например, 200+ архивов).)
1. **Клонирование репозитория:**
   ```bash
   git clone https://github.com/NVLev/indicator01
   cd indicator01
   ``` 
2.  **Настройка окружения:**
```bash
cp .env.template .env
# Отредактируйте .env при необходимости
```
3. **Запуск сервисов:**
####Перед первым запуском выполните сборку образов:
```bash
docker compose build
```
### Запуск БД и выполнение миграций:

```bash
docker compose --profile migrations up -d
```
- или пошагово
- 
```bash
# Запуск базы данных
docker compose up pg -d

# Выполнение миграций
docker compose --profile migrations run --rm alembic alembic upgrade head

# Запуск всех сервисов
docker compose up -d

# Просмотр логов
docker compose logs -f
docker compose logs -f backend
docker compose logs -f ml_service
docker compose logs -f celery_worker
```
4. Проверка работы:
   - Демо-интерфейс будет доступен по адресу: [http://localhost:8000/demo/](http://localhost:8000/demo/)  
   - Api интерфейс будет доступен по адресу - [http://localhost:8000/docs](http://localhost:8000/docs)
   - Подробную информацию о ходе обработке можно будет увидеть в логах, запустив 
     - - Для отслеживания работы модели
     ```bash
     
     docker compose logs -f backend
     docker compose logs -f ml_service
     docker compose logs -f
     docker compose logs -f celery_worker
     ```


---



## 📊 Функции API
### 🔐 Аутентификация
- `POST /auth/register` - Регистрация пользователя
- `POST /auth/login` - Авторизация и получение JWT токена
### 📁 Управление исследованиями

#### Загрузка исследований
- `POST /studies/upload` - Загрузка одного исследования (ZIP архив)
- `POST /studies/upload/bulk` - Массовая загрузка до 20 исследований

#### Получение информации об исследованиях
- `GET /studies/` - Список исследований пользователя с пагинацией
- `GET /studies/{study_id}` - Детальная информация о конкретном исследовании
- `GET /studies/{study_id}/progress` - Прогресс обработки исследования

#### Экспорт и визуализация
- `GET /studies/{study_id}/export` - Экспорт результатов в Excel (формат по ТЗ)
- `GET /studies/{study_id}/heatmap` - Получение PNG heatmap визуализации

#### Управление исследованиями
- `POST /studies/{study_id}/retry` - Повторная обработка неудачного исследования
- `DELETE /studies/{study_id}` - Удаление исследования и связанных файлов

- `POST /studies/upload` — загрузка исследования
- `GET /studies/{id}/progress` — прогресс обработки
- `GET /studies/{id}/heatmap` — визуализация heatmap
- `GET /studies/{id}/export` — экспорт в Excel
- `POST /studies/upload/bulk` — массовая загрузка (до 20 файлов)
- `POST /export/bulk` — массовый экспорт в Excel



---

## 🛡️ RAG система верификации
Для борьбы с ложными «нормами» реализован модуль **VerificationEngine**, который анализирует heatmap от модели и проверяет качество предсказания. Это особенно важно для случаев, когда модель может пропустить патологию.

**Проверяемые аспекты:**
- Фокус внимания на релевантных областях
- Отсутствие артефактов по краям изображения
- Информативность карты активации
- Распределение внимания модели

**Результаты верификации:**
- ✅ `accept_normal` — предсказание можно считать надёжным
- ⚠️ `manual_review_recommended` — рекомендуется проверка врачом  
- 🚨 `manual_review_required` — высокая вероятность ошибки модели

---

## 📁 Структура проекта
```bash
indicator01/
├── backend/                 # FastAPI приложение
│   ├── app/
│   │   ├── main.py         # Точка входа приложения
│   │   ├── routes/         # HTTP эндпоинты
│   │   │   ├── auth.py     # Аутентификация
│   │   │   ├── studies.py  # Управление исследованиями
│   │   │   └── demo.py     # Демо-интерфейс
│   │   ├── services/       # Бизнес-логика
│   │   │   ├── auth_service.py
│   │   │   ├── study_service.py
│   │   │   └── demo_service.py
│   │   ├── static/       # статические файлы
│   │   │  └──css.py/
│   │   ├── templstes/       # шаблоны для демо-версии
│   │   │   ├── demo_error.html
│   │   │   ├── demo_main.html
│   │   │   ├── demo_redirect.html
│   │   │   ├── demo_results.html
│   │   │   └── demo_study_detail.html
│   │   ├── core/           # Ядро приложения
│   │   │   ├── models.py   # SQLAlchemy модели
│   │   │   ├── schemas.py  # Pydantic схемы
│   │   │   └── config.py   # Конфигурация
│   │   └── templates/      # HTML шаблоны демо
│   ├── workers/
│   │   └── tasks.py        # Celery задачи
│   └── requirements_backend.txt
├── front_documentation/    # Документация для фронтенда
│   ├── api_spec.json
│   └── API_SPEC_FULL.md    # Подробная спецификация API
├── ML_model/               # ML модели и инференс
│   ├── Inference.py
│   ├── heatmap.py
│   └── ML_model.py
├── docker-compose.yml      # Оркестрация сервисов
├── Dockerfile             # Базовый образ
├── Dockerfile.ml          # ML сервис
└── .env.template          # Шаблон переменных окружения
```

## Авторские права и участие

### Автор проекта:
Natalia Levant — разработка архитектуры, бэкенда, API, документации и развёртывания
GitHub: https://github.com/NVLev

### Разработка ML-модели:
Data Scientist — AllexShv
GitHub: https://github.com/AllexShv
(архитектура и обучение модели для анализа КТ-изображений)

### Авторские права:
© 2025 Natalia Levant и соавторы.
Проект опубликован в образовательных и исследовательских целях.
Разрешено использование кода в некоммерческих проектах с обязательной ссылкой на авторов.
Для коммерческого использования требуется согласование с правообладателями.
