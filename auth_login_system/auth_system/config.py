# config.py
"""
Configuration for Auth System
Supports: Local development, Docker Compose, Testing, Production
With Redis password support for production security
"""
import os
import sys
from datetime import timedelta
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()


def build_redis_url(host=None, port=None, password=None, db=None, url_override=None):
    """
    Построение Redis URL с поддержкой пароля
    
    Args:
        host: Хост Redis (по умолчанию из окружения)
        port: Порт Redis (по умолчанию 6379)
        password: Пароль (опционально)
        db: Номер БД (по умолчанию 0)
        url_override: Прямой URL (имеет приоритет)
    
    Returns:
        str: Redis URL в формате redis://[:password@]host:port/db
    """
    # Приоритет 1: Явный URL из окружения
    if url_override:
        return url_override
    
    # Приоритет 2: Сборка из компонентов
    _host = host or os.environ.get('REDIS_HOST', 'localhost')
    _port = port or os.environ.get('REDIS_PORT', '6379')
    _password = password or os.environ.get('REDIS_PASSWORD')
    _db = db or os.environ.get('REDIS_DB', '0')
    
    # Экранируем спецсимволы в пароле для URL
    if _password:
        _password = quote_plus(_password)
        return f'redis://:{_password}@{_host}:{_port}/{_db}'
    else:
        return f'redis://{_host}:{_port}/{_db}'


class Config:
    """Base configuration"""
    
    # =============================================================================
    # Flask Core Settings
    # =============================================================================
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # =============================================================================
    # Database Settings (Docker-aware)
    # =============================================================================
    _db_url = os.environ.get('DATABASE_URL')
    if _db_url:
        SQLALCHEMY_DATABASE_URI = _db_url
    else:
        _db_user = os.environ.get('DB_USER', 'cubinez85')
        _db_pass = os.environ.get('DB_PASSWORD', '')
        _db_host = os.environ.get('DB_HOST', 'localhost')
        _db_port = os.environ.get('DB_PORT', '5432')
        _db_name = os.environ.get('DB_NAME', 'auth_system_db')
        
        if _db_pass:
            SQLALCHEMY_DATABASE_URI = f'postgresql://{_db_user}:{quote_plus(_db_pass)}@{_db_host}:{_db_port}/{_db_name}'
        else:
            SQLALCHEMY_DATABASE_URI = f'postgresql://{_db_user}@{_db_host}:{_db_port}/{_db_name}'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Настройки пула соединений (только для PostgreSQL)
    _is_sqlite = 'sqlite' in (os.environ.get('DATABASE_URL', '') or '').lower()
    if _is_sqlite:
        SQLALCHEMY_ENGINE_OPTIONS = {}
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': int(os.environ.get('DB_POOL_SIZE', 10)),
            'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 300)),
            'pool_pre_ping': os.environ.get('DB_POOL_PRE_PING', 'true').lower() in ('true', '1', 'yes'),
            'connect_args': {
                'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', 10)),
            }
        }
    
    # =============================================================================
    # JWT Settings
    # =============================================================================
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 900)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES', 604800)))
    
    # =============================================================================
    # Admin Settings
    # =============================================================================
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Admin123!')
    
    # =============================================================================
    # Security Settings
    # =============================================================================
    BCRYPT_LOG_ROUNDS = 13
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost,http://localhost:3000,http://cubinez.ru').split(',')
    
    # =============================================================================
    # Redis Settings (with password support)
    # =============================================================================
    
    # Базовые параметры Redis
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')  # Опционально
    REDIS_DB = os.environ.get('REDIS_DB', '0')
    
    # Основной REDIS_URL (для кэша, очередей и т.д.)
    REDIS_URL = build_redis_url(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        db=REDIS_DB,
        url_override=os.environ.get('REDIS_URL')
    )
    
    # Rate limiting: используем REDIS_URL или fallback на memory
    _ratelimit_url = os.environ.get('RATELIMIT_STORAGE_URL')
    if _ratelimit_url:
        RATELIMIT_STORAGE_URL = _ratelimit_url
    elif REDIS_PASSWORD or os.environ.get('REDIS_URL'):
        RATELIMIT_STORAGE_URL = REDIS_URL
    else:
        RATELIMIT_STORAGE_URL = 'memory://'
    
    # Flask-Caching настройки (опционально)
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = REDIS_URL
    CACHE_REDIS_DB = int(os.environ.get('CACHE_REDIS_DB', 1))  # Отдельная БД для кэша
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', 300))
    CACHE_KEY_PREFIX = os.environ.get('CACHE_KEY_PREFIX', 'auth_cache:')
    
    # =============================================================================
    # Logging Settings (Docker-aware)
    # =============================================================================
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    _is_docker = os.environ.get('RUNNING_IN_DOCKER', 'false').lower() in ('true', '1', 'yes')
    _log_to_file = os.environ.get('LOG_TO_FILE', 'true').lower() in ('true', '1', 'yes')
    
    if _is_docker or not _log_to_file:
        LOG_FILE = None
    else:
        LOG_FILE = os.environ.get('LOG_FILE', 'logs/app.log')
        _log_dir = os.path.dirname(LOG_FILE)
        if _log_dir and not os.path.exists(_log_dir):
            try:
                os.makedirs(_log_dir, exist_ok=True)
            except OSError:
                pass
    
    # =============================================================================
    # Email Settings (External SMTP Server)
    # =============================================================================
    MAIL_SERVER = os.environ.get('MAIL_SERVER', '95.174.94.246')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 25))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'false').lower() in ('true', '1', 'yes')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('true', '1', 'yes')
    
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'cubinez85@cubinez.ru')
    MAIL_RECIPIENT = os.environ.get('MAIL_RECIPIENT')
    
    # =============================================================================
    # Email Verification Settings
    # =============================================================================
    EMAIL_VERIFICATION_EXPIRES_HOURS = int(os.environ.get('EMAIL_VERIFICATION_EXPIRES_HOURS', 24))
    EMAIL_VERIFICATION_MIN_INTERVAL_MINUTES = int(os.environ.get('EMAIL_VERIFICATION_MIN_INTERVAL_MINUTES', 5))
    
    # =============================================================================
    # Password Reset Settings
    # =============================================================================
    PASSWORD_RESET_EXPIRES_HOURS = int(os.environ.get('PASSWORD_RESET_EXPIRES_HOURS', 1))
    PASSWORD_RESET_MIN_INTERVAL_MINUTES = int(os.environ.get('PASSWORD_RESET_MIN_INTERVAL_MINUTES', 15))
    
    # =============================================================================
    # Rate Limiting
    # =============================================================================
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'true').lower() in ('true', '1', 'yes')
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '100/hour')
    # RATELIMIT_STORAGE_URL уже установлен выше
    
    # =============================================================================
    # Base URL for Link Generation
    # =============================================================================
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:8084')
    
    # =============================================================================
    # Development Flags
    # =============================================================================
    MAIL_LOG_ONLY = os.environ.get('MAIL_LOG_ONLY', 'false').lower() in ('true', '1', 'yes')
    
    # =============================================================================
    # Helpers
    # =============================================================================
    @staticmethod
    def init_app(app):
        """Инициализация приложения с дополнительной конфигурацией"""
        pass


class DevelopmentConfig(Config):
    """Configuration for local development"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    MAIL_LOG_ONLY = os.environ.get('MAIL_LOG_ONLY', 'true').lower() in ('true', '1', 'yes')
    # В разработке можно отключить пароль Redis для удобства
    # REDIS_PASSWORD = None


class ProductionConfig(Config):
    """Configuration for production (Docker or host)"""
    DEBUG = False
    LOG_LEVEL = 'INFO'
    MAIL_LOG_ONLY = False
    LOG_TO_FILE = os.environ.get('LOG_TO_FILE', 'true').lower() in ('true', '1', 'yes')
    # В продакшене обязательно используйте REDIS_PASSWORD


class TestingConfig(Config):
    """
    Configuration for pytest tests
    Uses SQLite in-memory database, no external dependencies
    """
    TESTING = True
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}
    
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URL = 'memory://'
    
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    
    MAIL_LOG_ONLY = True
    LOG_FILE = None
    
    # В тестах не используем Redis
    REDIS_URL = None
    CACHE_TYPE = 'simple'


# =============================================================================
# Configuration Registry
# =============================================================================
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
