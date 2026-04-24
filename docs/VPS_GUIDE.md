# VPS Guide — BEST PR System

Сервер: `192.144.12.196` (Ubuntu 22.04)
Домен: `best-pr-system.ru`

---

## 1. Подключение к серверу

```bash
ssh misha_b@192.144.12.196
# Пароль: !passBESTmisha1 (или текущий)
```

После входа:

```bash
cd ~/best-pr-system
```

---

## 2. Управление сервисами

### Статус всех контейнеров

```bash
docker compose ps
```

### Запуск / остановка / перезапуск

```bash
# Запустить все сервисы
docker compose up -d

# Остановить все
docker compose down

# Перезапустить конкретный сервис
docker compose restart backend
docker compose restart frontend
docker compose restart postgres
```

### Полная пересборка (после изменений в коде)

```bash
docker compose up -d --build
```

---

## 3. Просмотр логов

```bash
# Бэкенд (API + бот) — в реальном времени
docker compose logs -f backend

# Последние 200 строк бэкенда
docker compose logs --tail=200 backend

# Фронтенд (nginx)
docker compose logs -f frontend

# База данных
docker compose logs -f postgres

# Все сервисы сразу
docker compose logs -f

# Поиск ошибок в логах
docker compose logs backend | grep -i error
docker compose logs backend | grep -i traceback
```

Для выхода из режима логов: `Ctrl+C`

---

## 4. Деплой новой версии

```bash
cd "BEST PR System"
git add .
git commit -m "Что я делаю не так в своей жизни?"
git push origin main
```

### Обычный деплой (после git push)

```bash
cd ~/best-pr-system
bash deploy/deploy.sh
```

Скрипт делает: `git pull` -> `docker compose build` -> `docker compose up -d` -> `alembic upgrade head`

### Ручной деплой (то же самое по шагам)

```bash
cd ~/best-pr-system
git pull origin main
docker compose up -d --build
docker compose exec backend python -m alembic upgrade head
```

---

## 5. Откат к предыдущей версии

### Если последний коммит сломал что-то

```bash
cd ~/best-pr-system

# Посмотреть историю коммитов
git log --oneline -10

# Откатить на 1 коммит назад
git checkout HEAD~1
docker compose up -d --build

# Откатить к конкретному коммиту (по хешу)
git checkout abc1234
docker compose up -d --build
```

### Вернуться обратно к последней версии

```bash
git checkout main
git pull origin main
docker compose up -d --build
```

---

## 6. База данных

### Подключиться к PostgreSQL

```bash
docker compose exec postgres psql -U best_pr_user -d best_pr_system
```

Полезные SQL-команды внутри psql:

```sql
-- Список таблиц
\dt

-- Количество пользователей
SELECT count(*) FROM users;

-- Посмотреть пользователя по telegram_id
SELECT id, full_name, role, is_active FROM users WHERE telegram_id = 772833280;

-- Изменить роль пользователя
UPDATE users SET role = 'admin' WHERE telegram_id = 772833280;

-- Выход
\q
```

### Бэкап базы данных

```bash
# Создать дамп
docker compose exec postgres pg_dump -U best_pr_user -d best_pr_system -Fc > backup_$(date +%Y%m%d).sql

# Восстановить из дампа
docker compose exec -T postgres pg_restore -U best_pr_user -d best_pr_system --no-owner --no-acl < backup_20260326.sql
```

### Миграции (Alembic)

```bash
# Применить все миграции
docker compose exec backend python -m alembic upgrade head

# Посмотреть текущую версию
docker compose exec backend python -m alembic current

# Откатить последнюю миграцию
docker compose exec backend python -m alembic downgrade -1
```

---

## 7. Переменные окружения

Все переменные хранятся в файле `.env` в корне проекта:

```bash
nano ~/best-pr-system/.env
```

После изменения `.env` перезапустить:

```bash
docker compose up -d
```

Если изменился код (не только .env):

```bash
docker compose up -d --build
```

---

## 8. nginx и SSL

### Проверить конфигурацию nginx

```bash
sudo nginx -t
```

### Перезагрузить nginx

```bash
sudo systemctl reload nginx
```

### Обновить SSL-сертификат (автоматически по cron, но можно вручную)

```bash
sudo certbot renew
```

### Конфигурация сайта

```bash
sudo nano /etc/nginx/sites-available/best-pr
sudo nginx -t && sudo systemctl reload nginx
```

---

## 9. Мониторинг ресурсов

```bash
# RAM и CPU
htop
# или
free -h && df -h / && docker stats --no-stream

# Место на диске
df -h /

# Размер Docker образов
docker system df

# Очистка неиспользуемых Docker образов (освободить место)
docker system prune -f
```

---

## 10. Экстренные ситуации

### Сервис не стартует

```bash
# Посмотреть, что случилось
docker compose logs --tail=50 backend

# Перезапустить с нуля
docker compose down
docker compose up -d --build
```

### Нет места на диске

```bash
# Удалить старые Docker образы и кэш
docker system prune -af

# Проверить, что занимает место
du -sh /var/lib/docker/
```

### PostgreSQL не запускается

```bash
docker compose logs postgres
# Если данные повреждены — восстановить из бэкапа:
docker compose down
docker volume rm best-pr-system_postgres_data
docker compose up -d
# Затем восстановить данные из бэкапа
```

### Нужно полностью пересоздать все контейнеры

```bash
docker compose down --rmi all
docker compose up -d --build
docker compose exec backend python -m alembic upgrade head
```

---

## 11. Автодеплой

Если настроен cron:

```bash
# Посмотреть текущие cron-задачи
crontab -l

# Редактировать
crontab -e
```

Пример записи для автодеплоя каждые 5 минут:

```
*/5 * * * * cd /home/misha_b/best-pr-system && git pull origin main && docker compose up -d --build >> /home/misha_b/deploy.log 2>&1
```

---

## 12. Полезные команды — шпаргалка


| Действие       | Команда                                                                                   |
| -------------- | ----------------------------------------------------------------------------------------- |
| Подключиться   | `ssh misha_b@192.144.12.196`                                                              |
| Статус         | `docker compose ps`                                                                       |
| Логи бэкенда   | `docker compose logs -f backend`                                                          |
| Деплой         | `bash deploy/deploy.sh`                                                                   |
| Откат          | `git checkout HEAD~1 && docker compose up -d --build`                                     |
| Перезапуск     | `docker compose restart backend`                                                          |
| Бэкап БД       | `docker compose exec postgres pg_dump -U best_pr_user -d best_pr_system -Fc > backup.sql` |
| Зайти в БД     | `docker compose exec postgres psql -U best_pr_user -d best_pr_system`                     |
| Миграции       | `docker compose exec backend python -m alembic upgrade head`                              |
| Место на диске | `df -h / && docker system df`                                                             |
| Очистка Docker | `docker system prune -f`                                                                  |


