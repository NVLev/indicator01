# 🚀 API Документация

## `POST /auth/register`
**Описание:** Register
### Тело запроса:
- `application/json`: #/components/schemas/UserCreate
### Ответы:
- `200`: Successful Response
- `422`: Validation Error

---

## `POST /auth/login`
**Описание:** Login
### Тело запроса:
- `application/json`: #/components/schemas/LoginRequest
### Ответы:
- `200`: Successful Response
- `422`: Validation Error

---

## `POST /auth/refresh`
**Описание:** Refresh
### Параметры:
- `refresh_token` (query, string) [обязательный]
### Ответы:
- `200`: Successful Response
- `422`: Validation Error

---

## `POST /auth/logout`
**Описание:** Logout
### Тело запроса:
- `application/json`: #/components/schemas/RefreshTokenRequest
### Ответы:
- `200`: Successful Response
- `422`: Validation Error

---

## `GET /auth/me`
**Описание:** Get Me
### Ответы:
- `200`: Successful Response

---

## `POST /studies/upload`
**Описание:** Загрузить исследование
Загрузка ZIP-архива с DICOM исследованием для автоматического анализа ИИ

- Максимальный размер файла: 500MB
- Формат: ZIP архив с DICOM файлами
- Обработка занимает до 10 минут
### Тело запроса:
- `multipart/form-data`: #/components/schemas/Body_upload_study_studies_upload_post
### Ответы:
- `200`: Successful Response
- `422`: Validation Error

---

## `GET /studies/`
**Описание:** Список исследований
Получить список исследований пользователя с пагинацией

- page: Номер страницы (начинается с 1)
- per_page: Количество исследований на странице (макс. 100)
### Параметры:
- `page` (query, integer) 
- `per_page` (query, integer) 
### Ответы:
- `200`: Successful Response
- `422`: Validation Error

---

## `GET /studies/{study_id}`
**Описание:** Информация об исследовании
Получить детальную информацию о конкретном исследовании
### Параметры:
- `study_id` (path, integer) [обязательный]
### Ответы:
- `200`: Successful Response
- `422`: Validation Error

---

## `DELETE /studies/{study_id}`
**Описание:** Удалить исследование
Удалить исследование и все связанные файлы
### Параметры:
- `study_id` (path, integer) [обязательный]
### Ответы:
- `200`: Successful Response
- `422`: Validation Error

---

## `GET /studies/{study_id}/progress`
**Описание:** Прогресс обработки
Получить детальный прогресс выполнения задачи обработки

Возвращает текущий статус, процент выполнения и сообщение о состоянии
### Параметры:
- `study_id` (path, integer) [обязательный]
### Ответы:
- `200`: Successful Response
- `422`: Validation Error

---

## `POST /studies/{study_id}/retry`
**Описание:** Повторить обработку
Повторить обработку исследования после неудачной попытки

Доступно только для исследований со статусом FAILED
### Параметры:
- `study_id` (path, integer) [обязательный]
### Ответы:
- `200`: Successful Response
- `422`: Validation Error

---

## `GET /studies/{study_id}/export`
**Описание:** Экспорт в Excel
Экспорт результатов исследования в Excel файл согласно ТЗ

Формат соответствует требованиям технического задания
### Параметры:
- `study_id` (path, integer) [обязательный]
### Ответы:
- `200`: Successful Response
- `422`: Validation Error

---

## `GET /studies/{study_id}/heatmap`
**Описание:** Получить heatmap визуализацию
Получить PNG визуализацию heatmap для исследования

- Возвращает PNG изображение с визуализацией heatmap
- Показывает области, которые модель считает аномальными
- Используется для объяснения решения ИИ врачу
### Параметры:
- `study_id` (path, integer) [обязательный]
### Ответы:
- `200`: Successful Response
- `422`: Validation Error

---
