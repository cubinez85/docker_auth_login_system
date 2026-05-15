import jwt
from datetime import datetime, timedelta
from config import Config
from app import db

# Импорт TokenBlacklist с обработкой возможного отсутствия файла
try:
    from app.models.token import TokenBlacklist
except ImportError:
    from app.models import TokenBlacklist

def generate_tokens(user_id):
    """Generate access and refresh tokens"""
    now = datetime.utcnow()
    
    access_token = jwt.encode(
        {
            'user_id': user_id,
            'type': 'access',
            'exp': now + Config.JWT_ACCESS_TOKEN_EXPIRES,
            'iat': now
        },
        Config.JWT_SECRET_KEY,
        algorithm='HS256'
    )

    refresh_token = jwt.encode(
        {
            'user_id': user_id,
            'type': 'refresh',
            'exp': now + Config.JWT_REFRESH_TOKEN_EXPIRES,
            'iat': now
        },
        Config.JWT_SECRET_KEY,
        algorithm='HS256'
    )

    return {'access_token': access_token, 'refresh_token': refresh_token}

def decode_token(token):
    """Декодирует токен и проверяет blacklist"""
    try:
        if TokenBlacklist.is_blacklisted(token):
            return {'error': 'Token blacklisted', 'status': 'fail'}
        
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return {'error': 'Signature expired', 'status': 'fail'}
    except jwt.InvalidTokenError:
        return {'error': 'Invalid token', 'status': 'fail'}

def verify_refresh_token(token):
    """Verify refresh token and return user_id"""
    try:
        if TokenBlacklist.is_blacklisted(token):
            return None
        data = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        if data.get('type') != 'refresh':
            return None
        return data.get('user_id')
    except jwt.PyJWTError:
        return None

def blacklist_token(token, expires_at):
    """Добавляет токен в черный список"""
    try:
        if not TokenBlacklist.is_blacklisted(token):
            blacklisted_token = TokenBlacklist(token=token, expires_at=expires_at)
            db.session.add(blacklisted_token)
            db.session.commit()
            return True
        return True
    except Exception as e:
        db.session.rollback()
        return False

def get_token_expires(token):
    """Получает время истечения токена без проверки подписи"""
    try:
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        return datetime.fromtimestamp(unverified_payload['exp'])
    except:
        return datetime.utcnow() + Config.JWT_REFRESH_TOKEN_EXPIRES
