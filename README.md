📘 Auth System — Docker Deployment Guide (GitHub → Production)
Готовый шаблон документации для README.md или DEPLOYMENT.md.
Можно скопировать, вставить в репозиторий и использовать как чеклист развертывания.
📦 О проекте
Система аутентификации и авторизации на Flask с собственной JWT-реализацией, гибкой RBAC-моделью,
подтверждением email и восстановлением пароля.
Архитектура развёртывания:
🐳 auth_flask_app — Flask + Gunicorn в Docker
🗄️ auth_postgres — PostgreSQL 14 в Docker (persistent volume)
🌐 nginx — на хост-машине (SSL, Basic Auth, проксирование на 127.0.0.1:8084)
📧 SMTP — внешний сервер (95.174.94.246:25)
🛠 Требования
Компонент,Версия
Docker,20.10+
Docker Compose,v2.x
Git,2.30+
Nginx (на хосте),1.18+
Доступ к SMTP,Внешний сервер или локальный relay

Сборка и запуск Docker
# 1. Сборка образов
docker compose build --no-cache

# 2. Запуск сервисов в фоне
docker compose up -d

# 3. Проверка статуса (оба должны быть healthy)
docker compose ps

Инициализация базы данных
# Применение миграций внутри контейнера приложения
docker compose exec app flask db upgrade

# Опционально: создание администратора или тестовых данных
# docker compose exec app python scripts/seed_demo.py

Проверка работоспособности
# Health check приложения
curl -s http://127.0.0.1:8084/api/health/ | python3 -m json.tool

# Тест отправки письма (проверка SMTP из контейнера)
docker compose exec app python -c "
from app import create_app
from app.utils.email import send_email
app = create_app('production')
with app.app_context():
    print('✅ Email test:', send_email('your@email.com', 'Docker Test', '<h1>OK</h1>'))
"

# Тест регистрации и входа
curl -s -X POST http://127.0.0.1:8084/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@docker.ru","password":"DockerPass123!","confirm_password":"DockerPass123!","last_name":"Test","first_name":"Docker"}'

🔄 Управление контейнерами
Задача,Команда
Просмотр логов,docker compose logs -f app
Перезапуск приложения,docker compose restart app
Обновление кода,git pull && docker compose build app && docker compose up -d --no-deps app
Применение новых миграций,docker compose exec app flask db upgrade
Остановка (без удаления данных),docker compose down
Полная очистка (⚠️ удалит БД!),docker compose down -v
Доступ в shell,docker compose exec app bash
Доступ в psql,docker compose exec postgres psql -U auth_user -d auth_system

📘 Руководство по настройке панели Access Control
Полный промт-гайд для администраторов и разработчиков. Содержит архитектуру, пошаговую настройку, типовые сценарии,
диагностику и лучшие практики.

🎯 Назначение панели Access Control
Панель Access Control — центр управления разграничением прав в системе. Позволяет:
✅ Создавать ресурсы и действия
✅ Формировать разрешения (Resource:Action)
✅ Настраивать роли и назначать им права
✅ Привязывать роли к пользователям
✅ Переопределять права индивидуально (разрешить/запретить)
✅ Аудит и откат изменений

🗺️ Архитектура прав (схема БД)
Resource ──< Permission >── Action
                │
        ┌───────┴───────┐
        │               │
  RolePermission  UserPermission  ← приоритет над ролью
        │               │
        │               │
       Role ──< UserRole >── User

Таблица,Назначение,Ключевые поля
resources,Объекты системы,id", "name" (projects, documents), "description
actions,Операции,id", "name" (create, read, update, delete), "description
permissions,Комбинация Resource+Action,id", "resource_id", "action_id (уникальный составной ключ)
roles,Группы пользователей,id", "name" (Admin, Manager, User), "description", "is_system
user_roles,Привязка пользователя к роли,id", "user_id", "role_id", "assigned_at
role_permissions,Права роли,id", "role_id", "permission_id
user_permissions,Индивидуальные права (override),id", "user_id", "permission_id", "granted" (bool), "expires_at

Логика проверки прав (в порядке приоритета):
is_superuser=True → ✅ всегда разрешено
UserPermission (индивидуальное) → ✅/❌ переопределяет роль
RolePermission (через роль) → ✅/❌ стандартная проверка
По умолчанию → ❌ 403 Forbidden

⚙️ Пошаговая настройка в админке
1. Создание ресурсов
📍 Access Control → ➕ Create Resource
Name: projects
Description: Управление проектами
Повторите для documents, reports, settings и т.д.
2. Создание действий
📍 Access Control → ➕ Create Action
Name: create
Description: Создание объекта
Стандартный набор: create, read, update, delete, export, approve.
3. Генерация разрешений
📍 Access Control → ➕ Create Permission
Выбираете: Resource: projects + Action: create → projects:create
💡 Совет: создайте матрицу разрешений сразу после добавления ресурсов/действий.
4. Создание ролей
📍 Access Control → ➕ Create Role
Name: Admin
Description: Полный доступ ко всем ресурсам
is_system: ✅ (защита от случайного удаления)
Рекомендуемые роли: Admin, Manager, Editor, Viewer, Auditor.
5. Назначение прав ролям
📍 Access Control → ➕ Assign Permission to Role
Пример для Manager:
projects:create, projects:read, projects:update
documents:read, documents:create
❌ Не давать reports:* и settings:*
6. Привязка ролей к пользователям
📍 Access Control → ➕ Assign Role to User
Выбираете пользователя и роль. Можно назначать несколько ролей (суммируются права).
7. Индивидуальные переопределения (опционально)
📍 Access Control → ➕ Assign Permission to User
Пример: временно запретить конкретному менеджеру удалять проекты:
User: ivan@company.ru
Permission: projects:delete
✅ Granted: Снять галочку (явный запрет)
Expires at: 2026-06-01 (автоматический откат)

🔧 Типовые сценарии управления
Задача,Действия в админке
Дать доступ к отчетам только админам,1. Создать роль Admin<br>2. Назначить ей reports:*<br>3. Привязать пользователей к роли
Временно закрыть доступ пользователю,1. User Permissions → найти пользователя<br>2. Добавить granted=False для всех его ресурсов<br>3. Или сменить роль на Viewer
Создать роль "Аудитор" (только чтение),1. Роль Auditor<br>2. Права: *:read" (projects, documents, reports)"<br>3. ❌ Никаких create/update/delete
Срочно отозвать все права у пользователя,1. Удалить все записи в User Roles<br>2. Удалить все записи в User Permissions<br>3. Пользователь получит 403 на всех эндпоинтах
Проверить, почему пользователь получает 403,1. Открыть User Roles → проверить роль<br>2. Открыть Role Permissions → проверить права роли<br>3. Открыть User Permissions → проверить нет ли явного granted=False

🛡️ Безопасность и лучшие практики
Правило,Описание
🔒 Принцип наименьших привилегий,"Давать только те права, которые нужны для задачи"
🚫 Не редактировать права напрямую в БД,Использовать только админ-панель или API
📝 Вести журнал изменений,Включить логирование действий администраторов (app.admin.views → добавить audit log)
🔄 Регулярный аудит,Раз в месяц проверять User Permissions на наличие устаревших записей
⏳ Использовать `expires_at`,"Для временных доступов (стажеры, подрядчики, тестовые периоды)"
🧪 Тестировать права,Использовать /api/health/ и mock-эндпоинты для проверки 200/403
🛡️ Защищать системные роли,Флаг is_system=True + проверка в delete_model()

🚀 Быстрые команды для администратора
# Посмотреть права пользователя
docker compose exec app flask shell -c "
from app.models.user import User
from app.models.permission import UserRole, RolePermission, Permission, Resource, Action
u = User.query.filter_by(email='user@example.com').first()
roles = [ur.role.name for ur in u.roles]
print(f'Roles: {roles}')
"

# Сбросить кэш прав (если используется)
docker compose exec app flask cache clear

# Экспорт матрицы прав в CSV
docker compose exec app python scripts/export_permissions.py > permissions_matrix.csv
