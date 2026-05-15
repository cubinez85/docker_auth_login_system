from app import db
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    # Personal info
    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100))

    # Status
    is_active = db.Column(db.Boolean, default=False)  # ← Изменено: по умолчанию False
    is_superuser = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)  # ← Новый: подтверждён ли email

    # Password reset
    reset_token = db.Column(db.String(255), unique=True, nullable=True, index=True)
    reset_token_sent_at = db.Column(db.DateTime, nullable=True)
    reset_token_expires_at = db.Column(db.DateTime, nullable=True)
    
    # Email verification
    verification_token = db.Column(db.String(255), unique=True, nullable=True, index=True)
    verification_sent_at = db.Column(db.DateTime, nullable=True)
    verification_expires_at = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)

    # Relationships
    roles = db.relationship('UserRole', back_populates='user', cascade='all, delete-orphan')
    permissions = db.relationship('UserPermission', back_populates='user', cascade='all, delete-orphan')

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = datetime.utcnow()

    def get_full_name(self):
        parts = [self.last_name, self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        return ' '.join(parts)
    
    # === Email Verification Methods ===
    
    def generate_verification_token(self, expires_hours=24):
        """Генерация токена подтверждения email"""
        self.verification_token = secrets.token_urlsafe(32)
        self.verification_sent_at = datetime.utcnow()
        self.verification_expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        return self.verification_token
    
    def verify_email(self, token):
        """Проверка и применение токена"""
        if not self.verification_token or self.verification_token != token:
            return False, 'Invalid token'
        
        if self.verification_expires_at and datetime.utcnow() > self.verification_expires_at:
            return False, 'Token expired'
        
        self.is_verified = True
        self.is_active = True  # Активируем аккаунт после подтверждения
        self.verification_token = None
        self.verification_sent_at = None
        self.verification_expires_at = None
        return True, 'Email verified successfully'
    
    def can_resend_verification(self, min_interval_minutes=5):
        """Проверка можно ли отправить письмо повторно"""
        if not self.verification_sent_at:
            return True
        elapsed = datetime.utcnow() - self.verification_sent_at
        return elapsed.total_seconds() > (min_interval_minutes * 60)
    
    def get_verification_link(self, base_url):
        """Генерация ссылки для подтверждения"""
        if not self.verification_token:
            return None
        return f"{base_url.rstrip('/')}/api/auth/verify-email/{self.verification_token}"

    def __repr__(self):
        return f'<User {self.email}>'

    # === Password Reset Methods (добавьте в конец класса User) ===

    def generate_password_reset_token(self, expires_hours=1):
        """Генерация токена для сброса пароля"""
        import secrets
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_sent_at = datetime.utcnow()
        self.reset_token_expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        return self.reset_token

    def verify_reset_token(self, token):
        """Проверка и применение токена сброса пароля"""
        if not self.reset_token or self.reset_token != token:
            return False, 'Invalid token'
    
        if self.reset_token_expires_at and datetime.utcnow() > self.reset_token_expires_at:
            return False, 'Token expired'
    
        # Токен валиден — возвращаем пользователя для смены пароля
        return True, 'Token valid'

    def reset_password(self, new_password):
        """Установка нового пароля и инвалидация токена"""
        self.password = new_password  # Хеширование через property
        self.reset_token = None
        self.reset_token_sent_at = None
        self.reset_token_expires_at = None
        return True

    def can_request_password_reset(self, min_interval_minutes=15):
        """Проверка можно ли запросить сброс пароля повторно"""
        if not self.reset_token_sent_at:
            return True
        elapsed = datetime.utcnow() - self.reset_token_sent_at
        return elapsed.total_seconds() > (min_interval_minutes * 60)

    def get_password_reset_link(self, base_url):
        """Генерация ссылки для сброса пароля"""
        if not self.reset_token:
            return None
        return f"{base_url.rstrip('/')}/api/auth/reset-password/{self.reset_token}"

    def get_password_reset_page_link(self, base_url):
        """Генерация ссылки на HTML-страницу сброса пароля"""
        if not self.reset_token:
            return None
        # Обратите внимание: /reset-password-page/ вместо /reset-password/
        return f"{base_url.rstrip('/')}/api/auth/reset-password-page/{self.reset_token}/"
