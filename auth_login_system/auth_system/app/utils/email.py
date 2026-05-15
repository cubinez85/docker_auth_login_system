"""
Email utility for sending verification and notification emails
Supports SMTP servers without AUTH extension
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, render_template_string
import logging
import re

logger = logging.getLogger(__name__)


def validate_email_address(email):
    """Базовая валидация email"""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def send_email(to_email, subject, html_body, text_body=None):
    """
    Отправка email через SMTP БЕЗ аутентификации
    Поддерживает серверы без AUTH extension
    """
    config = current_app.config
    
    # Режим логирования вместо отправки
    if config.get('MAIL_LOG_ONLY', False):
        logger.info(f"📧 [EMAIL LOG] To: {to_email}, Subject: {subject}")
        logger.info(f"📧 [EMAIL LOG] HTML preview:\n{html_body[:500]}...")
        return True
    
    # Валидация
    if not validate_email_address(to_email):
        logger.error(f"Invalid email: {to_email}")
        return False
    
    # Перенаправление на тестовый получатель
    test_recipient = config.get('MAIL_RECIPIENT')
    if test_recipient and test_recipient != to_email:
        logger.info(f"📧 Redirecting: {to_email} → {test_recipient}")
        to_email = test_recipient
    
    try:
        # Создание письма
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = config.get('MAIL_DEFAULT_SENDER', 'noreply@cubinez.ru')
        msg['To'] = to_email
        
        if text_body:
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        
        # Настройки
        mail_server = config.get('MAIL_SERVER', 'localhost')
        mail_port = int(config.get('MAIL_PORT', 25))
        
        logger.debug(f"Connecting to {mail_server}:{mail_port} (no AUTH)")
        
        # Подключение БЕЗ аутентификации
        server = smtplib.SMTP(mail_server, mail_port, timeout=30)
        
        # НЕ вызываем server.login() — сервер не поддерживает AUTH!
        
        # Отправка
        server.sendmail(msg['From'], [to_email], msg.as_string())
        server.quit()
        
        logger.info(f"✅ Email sent to {to_email}: {subject}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP AUTH not supported — ensure MAIL_USERNAME/PASSWORD are commented out")
        return False
    except smtplib.SMTPRecipientsRefused as e:
        logger.error(f"Recipient refused: {e}")
        logger.error("Ensure MAIL_DEFAULT_SENDER uses @cubinez.ru domain")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return False
    except ConnectionRefusedError:
        logger.error(f"Connection refused to {mail_server}:{mail_port}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__}: {e}")
        return False


def send_verification_email(user):
    """Отправка письма с подтверждением email"""
    if not user.verification_token:
        logger.error(f"No verification token for {user.email}")
        return False
    
    verification_link = user.get_verification_link(current_app.config.get('BASE_URL'))
    if not verification_link:
        return False
    
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Подтверждение email</title></head>
    <body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
        <div style="max-width:600px;margin:20px auto;padding:20px;background:#f9f9f9;border-radius:8px;">
            <div style="background:#4a90d9;color:white;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
                <h2 style="margin:0;">🔐 Подтверждение регистрации</h2>
            </div>
            <div style="padding:30px;background:white;border-radius:0 0 8px 8px;">
                <p>Здравствуйте, <strong>{{ user.get_full_name() }}</strong>!</p>
                <p>Спасибо за регистрацию в <strong>Auth System</strong>.</p>
                <p>Для активации аккаунта подтвердите ваш email:</p>
                <p style="text-align:center;">
                    <a href="{{ verification_link }}" style="background:#4a90d9;color:white;padding:12px 30px;text-decoration:none;border-radius:5px;display:inline-block;">✅ Подтвердить email</a>
                </p>
                <p><small>Или скопируйте ссылку:<br><code style="background:#e8e8e8;padding:5px;border-radius:3px;word-break:break-all;">{{ verification_link }}</code></small></p>
                <p><strong>⏰ Ссылка действительна {{ expires_hours }} часов.</strong></p>
                <p><small>Если не вы регистрировались — проигнорируйте это письмо.</small></p>
            </div>
            <div style="text-align:center;color:#666;font-size:12px;margin-top:20px;">
                Auth System © {{ year }}
            </div>
        </div>
    </body>
    </html>
    '''
    
    text_template = '''
Здравствуйте, {{ user.get_full_name() }}!

Спасибо за регистрацию в Auth System.

Для активации аккаунта перейдите по ссылке:
{{ verification_link }}

Ссылка действительна {{ expires_hours }} часов.

Если не вы регистрировались — проигнорируйте письмо.

---
Auth System © {{ year }}
    '''
    
    from datetime import datetime
    context = {
        'user': user,
        'verification_link': verification_link,
        'expires_hours': current_app.config.get('EMAIL_VERIFICATION_EXPIRES_HOURS', 24),
        'year': datetime.utcnow().year
    }
    
    html_body = render_template_string(html_template, **context)
    text_body = render_template_string(text_template, **context)
    
    subject = '🔐 Подтвердите ваш email в Auth System'
    
    return send_email(user.email, subject, html_body, text_body)

def send_password_reset_email(user):
    """
    Отправка письма для сброса пароля
    
    Args:
        user: Объект User с установленным reset_token
    
    Returns:
        bool: True если отправлено успешно
    """
    if not user.reset_token:
        logger.error(f"Cannot send reset: no token for user {user.email}")
        return False
    
    reset_link = user.get_password_reset_page_link(current_app.config.get('BASE_URL'))
    if not reset_link:
        return False
    
    # Шаблон письма
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Сброс пароля</title>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }
            .container { max-width: 600px; margin: 20px auto; padding: 0; }
            .header { background: #e74c3c; color: white; padding: 20px; text-align: center; }
            .content { background: #f9f9f9; padding: 30px; }
            .button { display: inline-block; background: #e74c3c; color: white; padding: 12px 30px; 
                     text-decoration: none; border-radius: 5px; margin: 20px 0; }
            .footer { text-align: center; color: #666; font-size: 12px; margin-top: 20px; }
            .code { background: #e8e8e8; padding: 5px 10px; border-radius: 3px; font-family: monospace; word-break: break-all; }
            .warning { background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px 15px; margin: 15px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">🔄 Сброс пароля</h2>
            </div>
            <div class="content">
                <p>Здравствуйте, <strong>{{ user.get_full_name() }}</strong>!</p>
                <p>Вы (или кто-то другой) запросили сброс пароля для аккаунта <strong>{{ user.email }}</strong>.</p>
                
                <p>Для установки нового пароля нажмите на кнопку ниже:</p>
                
                <p style="text-align: center;">
                    <a href="{{ reset_link }}" class="button">🔄 Сбросить пароль</a>
                </p>
                
                <p>Или скопируйте эту ссылку в браузер:</p>
                <p><span class="code">{{ reset_link }}</span></p>
                
                <div class="warning">
                    <strong>⏰ Ссылка действительна {{ expires_hours }} час(ов).</strong><br>
                    Если вы не запрашивали сброс пароля — просто проигнорируйте это письмо. Ваш аккаунт в безопасности.
                </div>
                
                <p><strong>🔐 В целях безопасности:</strong></p>
                <ul>
                    <li>Никогда не передавайте эту ссылку другим людям</li>
                    <li>После сброса пароля все активные сессии будут завершены</li>
                    <li>Рекомендуем использовать надёжный пароль (мин. 8 символов, буквы + цифры)</li>
                </ul>
            </div>
            <div class="footer">
                <p>Auth System © {{ year }}<br>
                Это автоматическое письмо, пожалуйста не отвечайте на него.</p>
            </div>
        </div>
    </body>
    </html>
    '''
    
    text_template = '''
Здравствуйте, {{ user.get_full_name() }}!

Вы запросили сброс пароля для аккаунта {{ user.email }}.

Для установки нового пароля перейдите по ссылке:
{{ reset_link }}

Ссылка действительна {{ expires_hours }} час(ов).

Если вы не запрашивали сброс пароля — проигнорируйте это письмо.

---
Auth System © {{ year }}
    '''
    
    from datetime import datetime
    context = {
        'user': user,
        'reset_link': reset_link,
        'expires_hours': current_app.config.get('PASSWORD_RESET_EXPIRES_HOURS', 1),
        'year': datetime.utcnow().year
    }
    
    html_body = render_template_string(html_template, **context)
    text_body = render_template_string(text_template, **context)
    
    subject = '🔄 Сброс пароля - Auth System'
    
    return send_email(user.email, subject, html_body, text_body)
