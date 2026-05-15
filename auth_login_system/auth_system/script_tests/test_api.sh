#!/bin/bash

BASE_URL="http://127.0.0.1:8000"
echo "Testing Auth System API"
echo "========================"

# 1. Регистрация нового пользователя
echo -e "\n1. Registering new user..."
curl -s -X POST $BASE_URL/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@example.com",
    "password": "Test123!",
    "confirm_password": "Test123!",
    "last_name": "Test",
    "first_name": "User",
    "middle_name": "Middle"
  }' | json_pp || echo "Failed to register"

# 2. Логин администратора
echo -e "\n2. Logging in as admin..."
ADMIN_RESPONSE=$(curl -s -X POST $BASE_URL/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "Admin123!"}')
echo $ADMIN_RESPONSE | json_pp

# Извлекаем токен
ADMIN_TOKEN=$(echo $ADMIN_RESPONSE | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -n "$ADMIN_TOKEN" ]; then
    echo "✅ Admin token obtained"
    
    # 3. Получение списка пользователей (admin only)
    echo -e "\n3. Getting users list (admin)..."
    curl -s -X GET $BASE_URL/api/admin/users \
      -H "Authorization: Bearer $ADMIN_TOKEN" | json_pp
    
    # 4. Получение списка проектов
    echo -e "\n4. Getting projects..."
    curl -s -X GET $BASE_URL/api/projects \
      -H "Authorization: Bearer $ADMIN_TOKEN" | json_pp
    
    # 5. Создание проекта (admin/manager)
    echo -e "\n5. Creating project..."
    curl -s -X POST $BASE_URL/api/projects \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"name": "Test Project"}' | json_pp
else
    echo "❌ Failed to get admin token"
fi

echo -e "\n========================"
echo "Tests completed"
