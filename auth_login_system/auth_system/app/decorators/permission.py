from functools import wraps
from flask import request, jsonify, g
import jwt
from config import Config

# ✅ Импортируем db
from app import db

# ✅ Импортируем модели из ПРАВИЛЬНЫХ файлов
from app.models.user import User
from app.models.permission import (
    UserRole, Role, Permission, 
    UserPermission, RolePermission, 
    Resource, Action
)


def token_required(f):
    """Decorator: требует валидный JWT токен"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]  # Bearer <token>
            except IndexError:
                return jsonify({'message': 'Invalid token format'}), 401

        if not token:
            return jsonify({'message': 'Token is missing'}), 401

        try:
            data = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
            current_user = User.query.filter_by(id=data['user_id'], is_active=True).first()

            if not current_user:
                return jsonify({'message': 'User not found or inactive'}), 401

            g.current_user = current_user

        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token'}), 401

        return f(*args, **kwargs)
    return decorated


def permission_required(resource_name, action_name):
    """Decorator: требует право resource:action"""
    def decorator(f):
        @wraps(f)
        @token_required
        def decorated_function(*args, **kwargs):
            user = g.current_user

            # Суперпользователь имеет все права
            if user.is_superuser:
                return f(*args, **kwargs)

            # Находим разрешение по resource:action
            permission = db.session.query(Permission)\
                .join(Resource)\
                .join(Action)\
                .filter(Resource.name == resource_name)\
                .filter(Action.name == action_name)\
                .first()

            if not permission:
                return jsonify({'message': f'Permission not found: {resource_name}:{action_name}'}), 403

            # 1. Проверка индивидуальных разрешений пользователя (приоритет)
            user_permission = UserPermission.query\
                .filter_by(user_id=user.id, permission_id=permission.id)\
                .first()

            if user_permission:
                if user_permission.granted:
                    return f(*args, **kwargs)
                else:
                    return jsonify({'message': 'Access denied by user-specific permission'}), 403

            # 2. Проверка разрешений через роли
            user_roles = UserRole.query.filter_by(user_id=user.id).all()
            role_ids = [ur.role_id for ur in user_roles]

            if role_ids:
                role_permission = RolePermission.query\
                    .filter(RolePermission.role_id.in_(role_ids))\
                    .filter(RolePermission.permission_id == permission.id)\
                    .first()

                if role_permission:
                    return f(*args, **kwargs)

            return jsonify({'message': 'Access denied'}), 403

        return decorated_function
    return decorator


def admin_required(f):
    """Decorator: требует роль Admin или is_superuser"""
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        user = g.current_user
        
        if user.is_superuser:
            return f(*args, **kwargs)
        
        admin_role = Role.query.filter_by(name='Admin').first()
        if admin_role:
            user_admin = UserRole.query.filter_by(user_id=user.id, role_id=admin_role.id).first()
            if user_admin:
                return f(*args, **kwargs)
        
        return jsonify({'message': 'Admin access required'}), 403
    return decorated
