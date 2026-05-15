# tests/conftest.py
"""
Pytest configuration and fixtures for Auth System tests
"""
import os
import sys
import pytest

# Добавляем корень проекта в Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.user import User
from app.models.permission import Role, UserRole, Resource, Action, Permission, RolePermission
from app.models.token import TokenBlacklist


@pytest.fixture(scope='session')
def app():
    """Создание Flask приложения для тестов"""
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        
        # Создаём тестовые роли и разрешения
        _create_test_data()
        
        yield app
        db.session.remove()
        db.drop_all()


def _create_test_data():
    """Создание тестовых данных (роли, разрешения)"""
    try:
        # Ресурсы
        for r_name in ['projects', 'documents', 'reports']:
            resource = Resource.query.filter_by(name=r_name).first()
            if not resource:
                resource = Resource(name=r_name, description=f'{r_name} resource')
                db.session.add(resource)
        
        # Действия
        for a_name in ['create', 'read', 'update', 'delete']:
            action = Action.query.filter_by(name=a_name).first()
            if not action:
                action = Action(name=a_name, description=f'{a_name} action')
                db.session.add(action)
        
        # Разрешения
        for resource in Resource.query.all():
            for action in Action.query.all():
                perm = Permission.query.filter_by(
                    resource_id=resource.id,
                    action_id=action.id
                ).first()
                if not perm:
                    perm = Permission(resource_id=resource.id, action_id=action.id)
                    db.session.add(perm)
        
        # Роли
        for role_name in ['Admin', 'Manager', 'User']:
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                role = Role(name=role_name, description=f'{role_name} role')
                db.session.add(role)
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        pytest.fail(f"Failed to create test data: {str(e)}")


@pytest.fixture(scope='function')
def client(app):
    """Test client для HTTP запросов"""
    return app.test_client()


@pytest.fixture(scope='function')
def test_user(client):
    """Создание тестового пользователя"""
    user_data = {
        'email': f'testuser_{os.urandom(4).hex()}@example.com',
        'password': 'TestPass123!',
        'confirm_password': 'TestPass123!',
        'last_name': 'Test',
        'first_name': 'User'
    }
    client.post('/api/auth/register/', json=user_data)
    return user_data


@pytest.fixture(scope='function')
def auth_token(client, test_user):
    """Получение JWT токена для аутентифицированных запросов"""
    login_response = client.post('/api/auth/login/', json={
        'email': test_user['email'],
        'password': test_user['password']
    })
    return login_response.get_json()['access_token']


@pytest.fixture(scope='function')
def auth_headers(auth_token):
    """Заголовки для авторизованных запросов"""
    return {
        'Authorization': f'Bearer {auth_token}',
        'Content-Type': 'application/json'
    }
