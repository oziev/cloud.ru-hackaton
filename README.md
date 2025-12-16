# TestOps Copilot

**AI-ассистент для автоматизации работы QA-инженера**

Автоматическая генерация тест-кейсов на основе требований и спецификаций с использованием Cloud.ru Evolution Foundation Model.

---

## Быстрый старт

### Требования
- Docker и Docker Compose (версия 2.0+)
- API ключ для Cloud.ru Evolution Foundation Model

**Примечание:** PostgreSQL и Redis запускаются автоматически через Docker Compose, отдельная установка не требуется.

### Запуск проекта

**Шаг 1: Клонирование и настройка**

```bash
# Переход в директорию проекта
cd testops_copilot

# Настройка API ключа (создайте файл .env или используйте переменные окружения)
export CLOUD_RU_API_KEY="your_api_key_here"
# Или создайте .env файл:
# echo "CLOUD_RU_API_KEY=your_api_key_here" > .env
```

**Шаг 2: Запуск всех сервисов**

```bash
# Запуск всех сервисов в фоновом режиме
docker-compose up -d

# Ожидание инициализации (30-60 секунд)
sleep 30

# Проверка статуса
docker-compose ps
```

**Шаг 3: Проверка работоспособности**

```bash
# Проверка API Gateway
curl http://localhost:8000/health

# Открыть API документацию
open http://localhost:8000/docs

# Открыть Frontend
open http://localhost:3000
```

**Шаг 4: Первый тест**

Через Frontend (http://localhost:3000):
1. Перейдите на страницу "Генерация"
2. Выберите вкладку "UI Тесты"
3. Введите URL: `https://cloud.ru/calculator`
4. Добавьте требования
5. Нажмите "Сгенерировать тесты"
6. Перейдите на страницу "Задачи" для отслеживания прогресса

Или через API:
```bash
curl -X POST "http://localhost:8000/api/v1/generate/test-cases" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://cloud.ru/calculator",
    "requirements": ["Проверить главную страницу"],
    "test_type": "both"
  }'
```

### Остановка проекта

```bash
# Остановка всех сервисов
docker-compose down

# Остановка с удалением volumes (удалит все данные)
docker-compose down -v
```

### Просмотр логов

```bash
# Логи всех сервисов
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f api_gateway
docker-compose logs -f celery_worker
docker-compose logs -f frontend
```

### Дополнительные проверки

```bash
# Проверка базы данных
docker-compose exec postgres psql -U testops -d testops_copilot -c "SELECT 1;"

# Проверка Redis
docker-compose exec redis redis-cli ping

# Flower (Celery monitoring)
open http://localhost:5555
```

**Примечание:** База данных автоматически инициализируется при первом запуске через `scripts/init_db.sql`. Если нужно пересоздать схему, используйте `docker-compose down -v && docker-compose up -d`.

---

## Основные возможности

### Генерация тестов

#### 1. Генерация ручных тест-кейсов для UI (15+ кейсов)
- Анализ веб-страницы через Playwright
- Генерация ручных тест-кейсов в формате Allure TestOps as Code
- Описание шагов теста в docstring
- Декоратор @allure.manual

**Пример использования:**
```bash
POST /api/v1/generate/test-cases
{
  "url": "https://cloud.ru/calculator",
  "requirements": [
    "Проверить отображение главной страницы",
    "Проверить расчет цены при добавлении сервиса"
  ],
  "test_type": "manual",
  "options": {
    "manual_count": 15
  }
}
```

#### 2. Генерация ручных тест-кейсов для API VMs (15+ кейсов)
- Парсинг OpenAPI спецификации
- Генерация ручных тест-кейсов для API endpoints
- Покрытие CRUD операций

**Пример использования:**
```bash
POST /api/v1/generate/api-tests
{
  "openapi_url": "https://compute.api.cloud.ru/openapi.yaml",
  "endpoints": ["/api/v1/vms"],
  "test_types": ["positive"]
}
```

#### 3. Генерация автоматизированных e2e тестов (pytest + Playwright)
- Автоматический анализ структуры страницы
- Генерация Playwright тестов с Allure декораторами
- Паттерн AAA (Arrange-Act-Assert)
- Использование allure.step() для структурирования

**Пример использования:**
```bash
POST /api/v1/generate/test-cases
{
  "url": "https://cloud.ru/calculator",
  "requirements": ["Проверить главную страницу"],
  "test_type": "automated",
  "options": {
    "automated_count": 10
  }
}
```

#### 4. Генерация автоматизированных API тестов (pytest + httpx)
- Генерация pytest тестов для API endpoints
- Покрытие positive/negative/edge cases
- Использование httpx.AsyncClient
- Allure декораторы и attachments

**Пример использования:**
```bash
POST /api/v1/generate/api-tests
{
  "openapi_url": "https://compute.api.cloud.ru/openapi.yaml",
  "endpoints": ["/api/v1/vms"],
  "test_types": ["positive", "negative"]
}
```

### Валидация тест-кейсов
- **Многоуровневая валидация** - синтаксис, семантика, логика, безопасность
- **Проверка Allure декораторов** - наличие обязательных декораторов
- **Safety Guard** - защита от опасного кода (eval, exec, os.system и т.д.)
- **Детальный отчет** - список ошибок и рекомендаций

### Валидация и оптимизация
- **Многоуровневая валидация** - синтаксис, семантика, логика, безопасность
- **Дедупликация** - поиск и удаление дубликатов тестов
- **Анализ покрытия** - проверка соответствия требованиям

### Интеграции
- **GitHub/GitLab** - автоматический commit тестов в репозиторий
- **Jira/Allure TestOps** - интеграция с системами управления тестами
- **Email уведомления** - оповещения о завершении генерации

### Мониторинг
- **Real-time обновления** - Server-Sent Events для отслеживания прогресса
- **Prometheus метрики** - мониторинг производительности
- **Логирование** - детальные логи всех операций

---

## Архитектура

Проект построен на микросервисной архитектуре:

```
┌─────────────┐
│   Frontend  │  React 19 + TypeScript
└──────┬──────┘
       │
┌──────▼──────┐
│ API Gateway │  FastAPI - единая точка входа
└──────┬──────┘
       │
   ┌───┴───┐
   │       │
┌──▼──┐ ┌─▼────┐
│Redis│ │Celery│  Асинхронная обработка
└──┬──┘ └─┬────┘
   │      │
┌──▼──────▼──┐
│  Workers   │  Генерация, валидация, оптимизация
└──────┬─────┘
       │
┌──────▼──────┐
│   Agents    │  AI-агенты для различных задач
└──────┬──────┘
       │
┌──────▼──────┐
│ PostgreSQL  │  Хранение данных и checkpoints
└─────────────┘
```

### Компоненты

**API Gateway** (`api_gateway/`)
- FastAPI приложение
- REST API endpoints
- Middleware (CORS, rate limiting, logging)
- SSE streaming для real-time обновлений

**Workers** (`workers/`)
- Celery workers для асинхронной обработки
- Workflow генерации тестов
- LangGraph для оркестрации агентов

**Agents** (`agents/`)
- **ReconnaissanceAgent** - анализ веб-страниц
- **GeneratorAgent** - генерация тестов через LLM
- **ValidatorAgent** - валидация тестов
- **OptimizerAgent** - оптимизация и дедупликация
- **SafetyGuard** - проверка безопасности кода
- **TestPlanGeneratorAgent** - генерация тест-планов

**Shared** (`shared/`)
- Утилиты для работы с БД, Redis, LLM
- Конфигурация приложения
- Модели данных

---

## API Endpoints

### Генерация тестов

```bash
# Генерация UI тестов
POST /api/v1/generate/test-cases
{
  "url": "https://example.com",
  "requirements": ["Проверить главную страницу"],
  "test_type": "both",
  "use_langgraph": true
}

# Генерация API тестов
POST /api/v1/generate/api-tests
{
  "openapi_url": "https://api.example.com/openapi.json",
  "endpoints": ["/users", "/posts"]
}
```

### Управление задачами

```bash
# Получение статуса задачи
GET /api/v1/tasks/{task_id}?include_tests=true

# Возобновление workflow
POST /api/v1/tasks/{task_id}/resume
```

### Поиск и экспорт

```bash
# Поиск тестов
GET /api/v1/tests?search=calculator&test_type=automated&page=1

# Экспорт тестов
GET /api/v1/tests/export?format=zip&request_id={request_id}
```

### Валидация и оптимизация

```bash
# Валидация теста
POST /api/v1/validate/tests
{
  "test_code": "def test_example(): assert True",
  "validation_level": "full"
}

# Оптимизация тестов
POST /api/v1/optimize/tests
{
  "tests": [...],
  "requirements": [...]
}
```

Полная документация API доступна по адресу: `http://localhost:8000/docs`

---

## Примеры использования

### Пример 1: Генерация ручных тест-кейсов для UI калькулятора

```bash
curl -X POST "http://localhost:8000/api/v1/generate/test-cases" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://cloud.ru/calculator",
    "requirements": [
      "Проверить отображение главной страницы с пояснительным текстом",
      "Проверить кликабельность кнопки \"Добавить сервис\"",
      "Проверить динамический расчет цены при изменении параметров"
    ],
    "test_type": "manual",
    "options": {
      "manual_count": 15
    }
  }'
```

### Пример 2: Генерация автоматизированных e2e тестов

```bash
curl -X POST "http://localhost:8000/api/v1/generate/test-cases" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://cloud.ru/calculator",
    "requirements": [
      "Проверить главную страницу",
      "Проверить добавление сервиса"
    ],
    "test_type": "automated",
    "options": {
      "automated_count": 10
    }
  }'
```

### Пример 3: Генерация API тестов для VMs

```bash
curl -X POST "http://localhost:8000/api/v1/generate/api-tests" \
  -H "Content-Type: application/json" \
  -d '{
    "openapi_url": "https://compute.api.cloud.ru/openapi.yaml",
    "endpoints": ["/api/v1/vms"],
    "test_types": ["positive", "negative"]
  }'
```

### Пример 4: Проверка статуса задачи

```bash
# Получить request_id из ответа предыдущего запроса
curl "http://localhost:8000/api/v1/tasks/{request_id}?include_tests=true"
```

### Пример 5: Валидация теста

```bash
curl -X POST "http://localhost:8000/api/v1/validate/tests" \
  -H "Content-Type: application/json" \
  -d '{
    "test_code": "@allure.feature(\"Test\")\ndef test_example(): assert True",
    "validation_level": "full"
  }'
```

---

## Конфигурация

### Переменные окружения

Основные настройки можно задать через переменные окружения или файл `.env`:

**Обязательные:**
- `CLOUD_RU_API_KEY` - API ключ для Cloud.ru Evolution Foundation Model (можно получить в настройках проекта)

**Опциональные (имеют значения по умолчанию):**
- `DATABASE_URL` - URL базы данных (по умолчанию: `postgresql://testops:testops_password@localhost:5432/testops_copilot`)
- `REDIS_URL` - URL Redis (по умолчанию: `redis://localhost:6379/0`)
- `CLOUD_RU_FOUNDATION_MODELS_URL` - URL API Foundation Models (по умолчанию: `https://foundation-models.api.cloud.ru/v1`)
- `CLOUD_RU_DEFAULT_MODEL` - Модель по умолчанию (по умолчанию: `ai-sage/GigaChat3-10B-A1.8B`)

**Пример .env файла:**
```env
# Cloud.ru API (ОБЯЗАТЕЛЬНО)
CLOUD_RU_API_KEY=your_api_key_here

# Database (опционально, для локального запуска используйте localhost)
DATABASE_URL=postgresql://testops:testops_password@localhost:5432/testops_copilot

# Redis (опционально, для локального запуска используйте localhost)
REDIS_URL=redis://localhost:6379/0
```

**Примечание:** При запуске через `docker-compose` большинство настроек уже настроены в `docker-compose.yml`. Вам нужно только указать `CLOUD_RU_API_KEY`.

---

## Тестирование

### Запуск тестов

```bash
# Unit тесты
pytest tests/unit/

# Integration тесты
pytest tests/integration/

# Все тесты
pytest tests/
```

### Покрытие кода

```bash
pytest --cov=agents --cov=api_gateway --cov=workers tests/
```

---

## Документация

Подробная документация для разработчиков находится в папке `testops_copilot/docs/`:

- **[00_OVERVIEW.md](testops_copilot/docs/00_OVERVIEW.md)** - Общий обзор системы
- **[01_API_GATEWAY.md](testops_copilot/docs/01_API_GATEWAY.md)** - API Gateway
- **[02_WORKERS.md](testops_copilot/docs/02_WORKERS.md)** - Celery Workers
- **[03_AGENTS.md](testops_copilot/docs/03_AGENTS.md)** - AI-агенты
- **[04_SHARED.md](testops_copilot/docs/04_SHARED.md)** - Общие компоненты
- **[05_DATABASE.md](testops_copilot/docs/05_DATABASE.md)** - Модели базы данных
- **[06_TODO.md](testops_copilot/docs/06_TODO.md)** - Что осталось реализовать

---

## Разработка

### Структура проекта

```
testops_copilot/
├── api_gateway/          # FastAPI приложение
│   ├── routers/          # API endpoints
│   └── middleware/       # Middleware
├── workers/              # Celery workers
│   └── tasks/            # Асинхронные задачи
├── agents/               # AI-агенты
│   ├── generator/        # Генерация тестов
│   ├── validator/        # Валидация
│   ├── optimizer/        # Оптимизация
│   └── reconnaissance/   # Анализ страниц
├── shared/               # Общие компоненты
│   ├── config/           # Конфигурация
│   ├── models/           # Модели данных
│   └── utils/            # Утилиты
├── tests/                # Тесты
│   ├── unit/             # Unit тесты
│   └── integration/      # Integration тесты
└── docs/                 # Документация
```

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Запуск в режиме разработки

```bash
# API Gateway
uvicorn api_gateway.main:app --reload --port 8000

# Celery Worker
celery -A workers.celery_app worker --loglevel=info

# Flower (мониторинг Celery)
celery -A workers.celery_app flower --port=5555
```

---

## Мониторинг

### Prometheus метрики

```bash
curl http://localhost:8000/metrics
```

### Flower (Celery)

```bash
open http://localhost:5555
```

### Логи

```bash
# Логи API Gateway
docker-compose logs -f api_gateway

# Логи Workers
docker-compose logs -f celery_worker
```

---

## Отладка

### Проверка подключений

```bash
# Проверка БД
docker-compose exec postgres psql -U testops -d testops_copilot

# Проверка Redis
docker-compose exec redis redis-cli ping

# Проверка Celery
celery -A workers.celery_app inspect active
```

### Частые проблемы

**Проблема:** Ошибка подключения к БД
```bash
# Решение: Проверьте DATABASE_URL в .env
docker-compose restart postgres
```

**Проблема:** Celery задачи не выполняются
```bash
# Решение: Проверьте Redis и перезапустите worker
docker-compose restart redis celery_worker
```

---

## Статус проекта

### Реализовано

- [x] Генерация UI и API тестов
- [x] Валидация и оптимизация тестов
- [x] Интеграция с GitHub/GitLab
- [x] LangGraph workflow с checkpointing
- [x] Safety Guard (4 уровня защиты)
- [x] Поиск и фильтрация тестов
- [x] Экспорт тестов (ZIP, JSON, YAML)
- [x] Email уведомления
- [x] Real-time обновления (SSE)
- [x] Prometheus метрики
- [x] Unit и integration тесты

### В разработке

- [ ] JWT аутентификация
- [ ] API Keys управление
- [ ] Скриншоты элементов
- [ ] Redis RediSearch для vector search
- [ ] Grafana dashboards
- [ ] CI/CD pipelines

Полный список задач: [testops_copilot/docs/06_TODO.md](testops_copilot/docs/06_TODO.md)

---

## Вклад в проект

1. Fork проекта
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

---

## Лицензия

Проект разработан для Cloud.ru

---

## Контакты

- **Документация:** [testops_copilot/docs/](testops_copilot/docs/)
- **Issues:** Создайте issue в репозитории
- **API Docs:** http://localhost:8000/docs
