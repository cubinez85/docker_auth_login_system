from app.utils.email import send_verification_email, send_password_reset_email
from flask import Blueprint, request, jsonify, g, current_app, url_for, render_template
from app import db, limiter
from app.models.user import User
from app.models.token import TokenBlacklist
from app.utils.jwt_helper import (
    generate_tokens,
    verify_refresh_token,
    decode_token,
    blacklist_token,
    get_token_expires
)
from app.models.permission import UserRole, UserPermission
from datetime import datetime, timedelta
import re
import jwt
import secrets

# ВАЖНО: url_prefix задаётся ЗДЕСЬ, а не при регистрации в __init__.py
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# =============================================================================
# Валидаторы
# =============================================================================

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    if len(password) < 8:
        return False, 'Password must be at least 8 characters long'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter'
    if not re.search(r'\d', password):
        return False, 'Password must contain at least one number'
    return True, 'Password is valid'

def get_current_user():
    """Получает пользователя из JWT токена в заголовке Authorization"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None

    token = auth_header.split(" ")[1]
    payload = decode_token(token)

    if 'error' in payload or 'user_id' not in payload:
        return None

    user = User.query.filter_by(id=payload['user_id'], is_active=True).first()
    return user

# =============================================================================
# Эндпоинты регистрации и аутентификации
# =============================================================================

@auth_bp.route('/register/', methods=['POST'])
@limiter.limit("5/hour")
def register():
    data = request.get_json()
    
    required_fields = ['email', 'password', 'confirm_password', 'last_name', 'first_name']
    for field in required_fields:
        if not data or field not in data:
            return jsonify({'message': f'Missing field: {field}'}), 400

    if not validate_email(data['email']):
        return jsonify({'message': 'Invalid email format'}), 400

    # 🔍 Проверяем существует ли пользователь
    existing_user = User.query.filter_by(email=data['email']).first()
    
    if existing_user:
        # ✅ Если пользователь был soft-deleted — удаляем его полностью
        if not existing_user.is_active:
            try:
                # Удаляем связанные записи
                UserRole.query.filter_by(user_id=existing_user.id).delete()
                UserPermission.query.filter_by(user_id=existing_user.id).delete()
                
                # Удаляем самого пользователя
                db.session.delete(existing_user)
                db.session.commit()
                current_app.logger.info(f"🗑️ Removed soft-deleted user: {data['email']}")
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Failed to remove soft-deleted user: {e}")
                return jsonify({'message': 'Failed to process registration'}), 500
        else:
            # ❌ Если пользователь активен — нельзя зарегистрироваться
            return jsonify({'message': 'Email already registered'}), 409

    # Валидация пароля
    valid, message = validate_password(data['password'])
    if not valid:
        return jsonify({'message': message}), 400

    if data['password'] != data['confirm_password']:
        return jsonify({'message': 'Passwords do not match'}), 400

    # Создание нового пользователя
    user = User(
        email=data['email'],
        last_name=data['last_name'],
        first_name=data['first_name'],
        middle_name=data.get('middle_name', '')
    )
    user.password = data['password']
    
    # Генерация токена верификации
    user.generate_verification_token(
        expires_hours=current_app.config.get('EMAIL_VERIFICATION_EXPIRES_HOURS', 24)
    )

    try:
        db.session.add(user)
        db.session.commit()
        
        # Отправка письма с подтверждением
        email_sent = send_verification_email(user)
        
        return jsonify({
            'message': 'User registered successfully. Please check your email to verify your account.',
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.get_full_name(),
                'is_verified': user.is_verified
            },
            'email_sent': email_sent
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Registration failed: {str(e)}'}), 500

@auth_bp.route('/login/', methods=['POST'])
@limiter.limit("10/minute")
def login():
    """
    POST /api/auth/login/
    Вход в систему
    """
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Email and password required'}), 400

    user = User.query.filter_by(email=data['email']).first()

    if not user or not user.verify_password(data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401
    
    if not user.is_active:
        # Проверяем, подтверждён ли email
        if not user.is_verified:
            return jsonify({
                'message': 'Email not verified. Please check your inbox for verification link.',
                'can_resend': user.can_resend_verification(),
                'error_code': 'EMAIL_NOT_VERIFIED'
            }), 403
        return jsonify({'message': 'Account is inactive. Please contact support.'}), 403

    tokens = generate_tokens(user.id)

    return jsonify({
        'message': 'Login successful',
        'access_token': tokens['access_token'],
        'refresh_token': tokens['refresh_token'],
        'user': {
            'id': user.id,
            'email': user.email,
            'full_name': user.get_full_name(),
            'is_verified': user.is_verified
        }
    }), 200


@auth_bp.route('/refresh/', methods=['POST'])
@limiter.limit("5/minute")
def refresh():
    """
    POST /api/auth/refresh/
    Обновление access токена через refresh токен
    """
    data = request.get_json()

    if not data or not data.get('refresh_token'):
        return jsonify({'message': 'Refresh token required'}), 400

    user_id = verify_refresh_token(data['refresh_token'])
    if not user_id:
        return jsonify({'message': 'Invalid refresh token'}), 401

    user = User.query.get(user_id)
    if not user or not user.is_active:
        return jsonify({'message': 'User not found or inactive'}), 401

    tokens = generate_tokens(user.id)
    return jsonify({
        'access_token': tokens['access_token'],
        'refresh_token': tokens['refresh_token']
    }), 200


@auth_bp.route('/logout/', methods=['POST'])
@limiter.limit("30/minute")
def logout():
    """
    POST /api/auth/logout/
    Выход из системы с инвалидацией токена
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'message': 'Authorization header required'}), 400

    token = auth_header.split(" ")[1]
    payload = decode_token(token)

    if 'error' in payload and payload['error'] != 'Signature expired':
        return jsonify({'message': payload['error']}), 400

    expires_at = get_token_expires(token)
    if blacklist_token(token, expires_at):
        return jsonify({'message': 'Successfully logged out'}), 200
    else:
        return jsonify({'message': 'Logout failed'}), 500

# =============================================================================
# 🔐 Email Verification Endpoints (НОВЫЕ)
# =============================================================================

@auth_bp.route('/verify-email/<token>/', methods=['GET'])
@limiter.limit("10/hour")
def verify_email(token):
    """
    GET /api/auth/verify-email/<token>/
    Подтверждение email по токену из письма
    """
    user = User.query.filter_by(verification_token=token).first()
    
    if not user:
        return jsonify({'message': 'Invalid or expired verification link'}), 404
    
    success, message = user.verify_email(token)
    
    if not success:
        return jsonify({'message': message}), 400
    
    try:
        db.session.commit()
        return jsonify({
            'message': 'Email verified successfully! You can now login.',
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.get_full_name(),
                'is_verified': user.is_verified
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Verification failed: {str(e)}'}), 500


@auth_bp.route('/resend-verification/', methods=['POST'])
@limiter.limit("3/hour")
def resend_verification():
    """
    POST /api/auth/resend-verification/
    Повторная отправка письма с подтверждением email
    """
    data = request.get_json()
    
    if not data or not data.get('email'):
        return jsonify({'message': 'Email required'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    
    # Не раскрываем существует ли пользователь (безопасность)
    if not user:
        return jsonify({'message': 'If the email exists, verification link has been sent.'}), 200
    
    if user.is_verified:
        return jsonify({'message': 'Email already verified. You can login now.'}), 400
    
    if not user.can_resend_verification():
        minutes = current_app.config.get('EMAIL_VERIFICATION_MIN_INTERVAL_MINUTES', 5)
        return jsonify({
            'message': f'Please wait {minutes} minutes before requesting another verification email.',
            'error_code': 'RATE_LIMITED'
        }), 429
    
    # Генерация нового токена
    user.generate_verification_token(
        expires_hours=current_app.config.get('EMAIL_VERIFICATION_EXPIRES_HOURS', 24)
    )
    
    try:
        email_sent = send_verification_email(user)
        db.session.commit()
        
        return jsonify({
            'message': 'Verification email sent. Please check your inbox.',
            'email_sent': email_sent
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Failed to send email: {str(e)}'}), 500


@auth_bp.route('/verify-email-status/', methods=['GET'])
@limiter.limit("30/minute")
def verify_email_status():
    """
    GET /api/auth/verify-email-status/
    Проверка статуса верификации email (требует авторизации)
    """
    user = get_current_user()
    if not user:
        return jsonify({'message': 'Unauthorized'}), 401
    
    return jsonify({
        'email': user.email,
        'is_verified': user.is_verified,
        'is_active': user.is_active,
        'can_resend': user.can_resend_verification() if not user.is_verified else False
    }), 200

# =============================================================================
# 👤 Profile Management Endpoints
# =============================================================================

@auth_bp.route('/me/', methods=['GET'])
@limiter.limit("30/minute")
def get_current_user_info():
    """
    GET /api/auth/me/
    Получение данных текущего авторизованного пользователя
    """
    user = get_current_user()
    if not user:
        return jsonify({'message': 'Unauthorized or invalid token'}), 401
    
    return jsonify({
        'user': {
            'id': user.id,
            'email': user.email,
            'full_name': user.get_full_name(),
            'last_name': user.last_name,
            'first_name': user.first_name,
            'middle_name': user.middle_name,
            'is_verified': user.is_verified,
            'is_active': user.is_active,
            'is_superuser': user.is_superuser,
            'created_at': user.created_at.isoformat() if user.created_at else None
        }
    }), 200


@auth_bp.route('/profile/', methods=['PUT'])
@limiter.limit("10/minute")
def update_profile():
    """
    PUT /api/auth/profile/
    Обновление профиля: имя, фамилия, отчество
    """
    user = get_current_user()
    if not user:
        return jsonify({'message': 'Unauthorized or invalid token'}), 401

    data = request.get_json()

    if 'last_name' in data:
        user.last_name = data['last_name']
    if 'first_name' in data:
        user.first_name = data['first_name']
    if 'middle_name' in data:
        user.middle_name = data['middle_name']

    try:
        db.session.commit()
        return jsonify({
            'message': 'Profile updated successfully',
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.get_full_name()
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Update failed: {str(e)}'}), 500


@auth_bp.route('/profile/', methods=['DELETE'])
@limiter.limit("5/minute")
def delete_profile():
    """
    DELETE /api/auth/profile/
    Мягкое удаление аккаунта + инвалидация токенов
    """
    user = get_current_user()
    if not user:
        return jsonify({'message': 'Unauthorized'}), 401

    user.soft_delete()

    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(" ")[1]
        expires_at = get_token_expires(token)
        blacklist_token(token, expires_at)

    try:
        db.session.commit()
        return jsonify({'message': 'Account deactivated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Deletion failed: {str(e)}'}), 500


@auth_bp.route('/change-password/', methods=['POST'])
@limiter.limit("5/hour")
def change_password():
    """
    POST /api/auth/change-password/
    Смена пароля для авторизованного пользователя
    """
    user = get_current_user()
    if not user:
        return jsonify({'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    
    if not data or not data.get('current_password') or not data.get('new_password'):
        return jsonify({'message': 'Current password and new password required'}), 400
    
    # Проверка текущего пароля
    if not user.verify_password(data['current_password']):
        return jsonify({'message': 'Current password is incorrect'}), 401
    
    # Валидация нового пароля
    valid, message = validate_password(data['new_password'])
    if not valid:
        return jsonify({'message': message}), 400
    
    if data.get('confirm_new_password') != data['new_password']:
        return jsonify({'message': 'New passwords do not match'}), 400
    
    # Смена пароля
    try:
        user.password = data['new_password']
        db.session.commit()
        return jsonify({'message': 'Password changed successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Password change failed: {str(e)}'}), 500


# === НОВЫЕ ЭНДПОИНТЫ ДЛЯ СБРОСА ПАРОЛЯ ===

@auth_bp.route('/forgot-password/', methods=['POST'])
@limiter.limit("3/hour")  # Защита от перебора
def forgot_password():
    """
    POST /api/auth/forgot-password/
    Запрос на сброс пароля по email
    """
    data = request.get_json()
    
    if not data or not data.get('email'):
        return jsonify({'message': 'Email required'}), 400
    
    email = data['email'].strip().lower()
    user = User.query.filter_by(email=email).first()
    
    # ⚠️ Безопасность: не раскрываем существует ли пользователь
    # Всегда возвращаем 200 чтобы не помогать атакам на перебор email
    if not user:
        return jsonify({
            'message': 'If the email exists, a password reset link has been sent.'
        }), 200
    
    # Проверка интервала между запросами
    if not user.can_request_password_reset():
        minutes = current_app.config.get('PASSWORD_RESET_MIN_INTERVAL_MINUTES', 15)
        return jsonify({
            'message': f'Please wait {minutes} minutes before requesting another password reset.'
        }), 429
    
    # Генерация нового токена сброса
    user.generate_password_reset_token(
        expires_hours=current_app.config.get('PASSWORD_RESET_EXPIRES_HOURS', 1)
    )
    
    try:
        email_sent = send_password_reset_email(user)
        db.session.commit()
        
        # Логируем для админа (но не в ответе пользователю)
        if email_sent:
            current_app.logger.info(f"Password reset email sent to {email}")
        else:
            current_app.logger.warning(f"Failed to send password reset email to {email}")
        
        return jsonify({
            'message': 'If the email exists, a password reset link has been sent.',
            'email_sent': email_sent  # Только для отладки, в продакшене убрать
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Forgot password error for {email}: {str(e)}")
        return jsonify({'message': 'Failed to process request. Please try again later.'}), 500


@auth_bp.route('/reset-password/<token>/', methods=['GET'])
@limiter.limit("10/hour")
def reset_password_page(token):
    """
    GET /api/auth/reset-password/<token>/
    Страница/проверка токена для сброса пароля
    
    Возвращает информацию о токене для фронтенда
    """
    user = User.query.filter_by(reset_token=token).first()
    
    if not user:
        return jsonify({'message': 'Invalid or expired reset link'}), 404
    
    valid, message = user.verify_reset_token(token)
    
    if not valid:
        return jsonify({'message': message}), 400
    
    # Токен валиден — возвращаем информацию для фронтенда
    # (НЕ сбрасываем пароль здесь, только показываем форму)
    return jsonify({
        'message': 'Token valid. You can now set a new password.',
        'user': {
            'email': user.email,
            'full_name': user.get_full_name()
        },
        'token_valid_until': user.reset_token_expires_at.isoformat() if user.reset_token_expires_at else None
    }), 200


@auth_bp.route('/reset-password/<token>/', methods=['POST'])
@limiter.limit("5/hour")
def reset_password_submit(token):
    """
    POST /api/auth/reset-password/<token>/
    Установка нового пароля после проверки токена
    """
    data = request.get_json()
    
    if not data or not data.get('new_password') or not data.get('confirm_password'):
        return jsonify({'message': 'New password and confirmation required'}), 400
    
    new_password = data['new_password']
    confirm_password = data['confirm_password']
    
    # Валидация пароля (та же что при регистрации)
    valid, message = validate_password(new_password)
    if not valid:
        return jsonify({'message': message}), 400
    
    if new_password != confirm_password:
        return jsonify({'message': 'Passwords do not match'}), 400
    
    # Поиск пользователя по токену
    user = User.query.filter_by(reset_token=token).first()
    
    if not user:
        return jsonify({'message': 'Invalid or expired reset link'}), 404
    
    # Проверка токена
    valid, message = user.verify_reset_token(token)
    if not valid:
        return jsonify({'message': message}), 400
    
    # Смена пароля
    try:
        user.reset_password(new_password)
        db.session.commit()
        
        current_app.logger.info(f"Password reset successful for user {user.email}")
        
        return jsonify({
            'message': 'Password changed successfully! You can now login with your new password.',
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.get_full_name()
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Password reset failed for {user.email}: {str(e)}")
        return jsonify({'message': 'Failed to reset password. Please try again.'}), 500

@auth_bp.route('/reset-password-page/<token>/', methods=['GET'])
def reset_password_page_html(token):
    """
    GET /api/auth/reset-password-page/<token>/
    HTML страница для сброса пароля (красивая форма)
    """
    user = User.query.filter_by(reset_token=token).first()
    
    if not user:
        return render_template('reset_password_form.html', 
                             email='', 
                             token='', 
                             error='Invalid or expired reset link')
    
    valid, message = user.verify_reset_token(token)
    if not valid:
        return render_template('reset_password_form.html', 
                             email=user.email, 
                             token=token, 
                             error=message)
    
    return render_template('reset_password_form.html', 
                         email=user.email, 
                         token=token)

# =============================================================================
# Health Check
# =============================================================================

@auth_bp.route('/health/', methods=['GET'])
def health_check():
    """
    GET /api/auth/health/
    Проверка доступности auth сервиса
    """
    return jsonify({
        'status': 'ok',
        'service': 'auth_system',
        'timestamp': datetime.utcnow().isoformat()
    }), 200
