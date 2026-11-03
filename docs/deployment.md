# Руководство по развёртыванию

Это руководство описывает развёртывание Aerial Sentinel на продакшен-сервер.

---

## Предварительные требования

- Ubuntu Server 22.04+ (или аналогичный дистрибутив Linux)
- Docker и Docker Compose установлены
- Доменное имя (опционально, для HTTPS)
- Аккаунт Telegram с API-учётными данными
- Достаточное дисковое пространство (минимум 20GB рекомендуется)

---

## Подготовка сервера

### 1. Установка Docker

```bash
# Обновление системных пакетов
apt update && apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com | sh

# Добавление текущего пользователя в группу docker (опционально)
usermod -aG docker $USER

# Проверка установки
docker --version
docker compose version
```

### 2. Подготовка директории проекта

```bash
# Создание директории проекта
mkdir -p /opt/aerial-sentinel
cd /opt/aerial-sentinel
```

---

## Развёртывание проекта

### 1. Клонирование или загрузка проекта

```bash
# Вариант A: Клонирование из Git
git clone https://github.com/LernerF/OsintPlatform_project.git .

# Вариант B: Загрузка через rsync (с локальной машины)
rsync -azP \
  --exclude='.git/' \
  --exclude='node_modules/' \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='.pytest_cache/' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  ./ ваш-сервер:/opt/aerial-sentinel/
```

### 2. Конфигурация окружения

```bash
# Копирование шаблона окружения
cp .env.example .env

# Редактирование конфигурации
nano .env
```

**Обязательные настройки:**

```env
# Конфигурация Telegram
TELEGRAM_ENABLED=true
TELEGRAM_API_ID=ваш_api_id
TELEGRAM_API_HASH=ваш_api_hash
TELEGRAM_SESSION_NAME=telegram_sessions/sentinel

# AI-классификация (рекомендуется для продакшена)
OPENROUTER_API_KEY=ваш_openrouter_key

# Геокодирование (выберите одно)
GEOCODER_PROVIDER=yandex  # Рекомендуется для России
YANDEX_GEOCODER_API_KEY=ваш_yandex_key

# ИЛИ используйте бесплатный Nominatim
GEOCODER_PROVIDER=nominatim
```

### 3. Создание необходимых директорий

```bash
mkdir -p data telegram_sessions
chmod 700 telegram_sessions
```

### 4. Авторизация Telegram-сессии

```bash
# Запуск интерактивного входа
docker compose run --rm backend python -m app.cli.telegram_check login
```

Следуйте инструкциям для ввода номера телефона и кода подтверждения.

### 5. Запуск сервисов

```bash
# Сборка и запуск контейнеров
docker compose up -d --build

# Проверка статуса
docker compose ps

# Просмотр логов
docker compose logs -f backend
```

### 6. Проверка развёртывания

```bash
# Проверка здоровья API
curl http://127.0.0.1:8000/api/health

# Проверка статуса системы
curl http://127.0.0.1:8000/api/system/status
```

---

## Конфигурация HTTPS (Опционально)

### Использование Let's Encrypt с IP-адресом

Если у вас нет домена, вы можете получить сертификат для IP-адреса:

```bash
# Установка certbot
apt install -y certbot

# Получение сертификата (требует открытый порт 80)
certbot certonly --standalone --preferred-challenges http -d IP_ВАШЕГО_СЕРВЕРА

# Расположение сертификата
# /etc/letsencrypt/live/IP_ВАШЕГО_СЕРВЕРА/fullchain.pem
# /etc/letsencrypt/live/IP_ВАШЕГО_СЕРВЕРА/privkey.pem
```

### Конфигурация Nginx-шлюза

1. Скопируйте пример конфигурации:

```bash
cp public/nginx.conf.example public/nginx.conf
```

2. Отредактируйте `public/nginx.conf` и замените `YOUR_SERVER_IP_OR_DOMAIN` на ваш IP или домен.

3. Создайте файл паролей:

```bash
# Установка apache2-utils для htpasswd
apt install -y apache2-utils

# Создание файла паролей
htpasswd -c public/.htpasswd admin
# Введите пароль по запросу

# Безопасные права доступа
chmod 600 public/.htpasswd
```

4. Запустите с публичной конфигурацией:

```bash
docker compose -f docker-compose.yml -f docker-compose.public.yml up -d
```

### Обновление сертификата

Создайте systemd-таймер для автоматического обновления:

```bash
# Создание файла сервиса
sudo tee /etc/systemd/system/sentinel-certbot-renew.service > /dev/null << 'EOF'
[Unit]
Description=Обновление TLS-сертификата для Aerial Sentinel

[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew --quiet --deploy-hook "/usr/bin/docker exec aerial-sentinel-gateway nginx -s reload"
EOF

# Создание файла таймера
sudo tee /etc/systemd/system/sentinel-certbot-renew.timer > /dev/null << 'EOF'
[Unit]
Description=Проверка TLS-сертификата Aerial Sentinel дважды в день

[Timer]
OnCalendar=*-*-* 03,15:00:00
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Включение таймера
sudo systemctl daemon-reload
sudo systemctl enable --now sentinel-certbot-renew.timer
```

---

## Подключение источников

### Через UI

1. Откройте дашборд в браузере
2. Нажмите кнопку `+` в панели Источники
3. Выберите каналы/чаты из ваших Telegram-диалогов
4. Установите город и регион для каждого источника
5. Нажмите "Подключить"

### Массовый импорт

1. Подготовьте текстовый файл с одним username канала на строку:
   ```
   @channel_name
   @another_channel
   https://t.me/yet_another
   ```

2. Перейдите во вкладку "Система" в UI
3. Нажмите "Выбрать .txt" и выберите ваш файл
4. Установите город и регион по умолчанию
5. Нажмите "Подключить все"

---

## Обслуживание

### Просмотр логов

```bash
# Все сервисы
docker compose logs -f

# Конкретный сервис
docker compose logs -f backend
docker compose logs -f frontend
```

### Резервное копирование базы данных

```bash
# Создание бэкапа
sqlite3 data/app.db ".backup data/backup_$(date +%Y%m%d_%H%M%S).db"

# Или копирование всей директории данных
tar -czf backup_$(date +%Y%m%d).tar.gz data/ telegram_sessions/
```

### Обновление приложения

```bash
cd /opt/aerial-sentinel

# Получение последних изменений
git pull

# Пересборка и перезапуск
docker compose up -d --build

# Проверка логов
docker compose logs -f
```

### Мониторинг дискового пространства

```bash
# Проверка доступного места
df -h

# Проверка размера базы данных
du -sh data/

# Проверка использования диска контейнерами
docker system df
```

---

## Устранение неполадок

### Бэкенд не запускается

```bash
# Проверка логов
docker compose logs backend

# Частые проблемы:
# - Отсутствует файл .env
# - Неверные учётные данные Telegram
# - Повреждённый файл сессии (удалите и авторизуйтесь заново)
```

### Telegram не получает сообщения

```bash
# Проверка подключения к Telegram
docker compose exec backend python -m app.cli.telegram_check status

# Проверка активности FloodWait
docker compose exec backend curl -s http://localhost:8000/api/system/status | jq .telegram
```

### Ошибки геокодирования

```bash
# Проверка конфигурации геокодирования
docker compose exec backend curl -s http://localhost:8000/api/system/status | jq .geocoding

# Тестирование Яндекс-геокодера
curl "https://geocode-maps.yandex.ru/1.x/?apikey=ВАШ_КЛЮЧ&geocode=Москва&format=json"
```

### Ошибки блокировки базы данных

```bash
# Режим WAL SQLite должен быть включён
docker compose exec backend sqlite3 data/app.db "PRAGMA journal_mode;"

# Если не WAL, включите его:
docker compose exec backend sqlite3 data/app.db "PRAGMA journal_mode=WAL;"
```

---

## Чек-лист безопасности

- [ ] Файл `.env` имеет ограниченные права (`chmod 600 .env`)
- [ ] Директория Telegram-сессий защищена (`chmod 700 telegram_sessions`)
- [ ] База данных не в Git-репозитории
- [ ] HTTPS включён для публичного доступа
- [ ] Basic auth настроен на шлюзе
- [ ] Правила файрвола разрешают только необходимые порты (80, 443)
- [ ] Настроено регулярное резервное копирование базы данных
- [ ] Системные обновления применяются регулярно

---

## Вопросы масштабирования

Для высоконагруженных развёртываний (100+ активных источников):

- Рассмотрите PostgreSQL вместо SQLite
- Добавьте Redis для кэширования и очередей задач
- Используйте Celery или Dramatiq для фоновой обработки
- Развёртывайте несколько backend-воркеров за балансировщиком нагрузки
- Включите пулинг соединений к базе данных

Для текущего развёртывания на SQLite рекомендуются следующие лимиты:

- Максимум источников: 100
- Конкуррентные запросы OpenRouter: 8
- Конкуррентные запросы геокодирования: 3 (Яндекс) или 1 (Nominatim)
- Один процесс Uvicorn worker
