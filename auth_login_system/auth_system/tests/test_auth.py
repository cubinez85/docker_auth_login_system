import pytest
from app import create_app, db
from app.models.user import User
import json

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_register_success(client):
    response = client.post('/api/auth/register/',
        json={'email': 'test@example.com', 'password': 'TestPass123!',
              'confirm_password': 'TestPass123!', 'last_name': 'Test', 'first_name': 'User'})
    assert response.status_code == 201

def test_login_success(client):
    # Сначала регистрация
    client.post('/api/auth/register/',
        json={'email': 'test@example.com', 'password': 'TestPass123!',
              'confirm_password': 'TestPass123!', 'last_name': 'Test', 'first_name': 'User'})
    # Затем вход
    response = client.post('/api/auth/login/',
        json={'email': 'test@example.com', 'password': 'TestPass123!'})
    assert response.status_code == 200
    assert 'access_token' in response.get_json()

def test_unauthorized_access(client):
    response = client.get('/api/projects/')
    assert response.status_code == 401

def test_soft_delete(client):
    # Регистрация и вход
    client.post('/api/auth/register/',
        json={'email': 'delete@example.com', 'password': 'TestPass123!',
              'confirm_password': 'TestPass123!', 'last_name': 'Delete', 'first_name': 'Test'})
    login = client.post('/api/auth/login/',
        json={'email': 'delete@example.com', 'password': 'TestPass123!'})
    token = login.get_json()['access_token']
    
    # Удаление
    response = client.delete('/api/auth/profile/',
        headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200
    
    # Попытка входа после удаления
    login2 = client.post('/api/auth/login/',
        json={'email': 'delete@example.com', 'password': 'TestPass123!'})
    assert login2.status_code == 401
