# /home/cubinez85/auth_login_system/auth_system/test_email.py
#!/usr/bin/env python3
"""
Тест отправки письма через приложение
"""
import sys
sys.path.insert(0, '/home/cubinez85/auth_login_system/auth_system')

from app import create_app
from app.utils.email import send_email

def test_send_email():
    app = create_app('development')
    
    with app.app_context():
        print("📧 Sending test email...")
        
        html_body = '''
        <html><body>
            <h2>✅ Тестовое письмо</h2>
            <p>Если вы видите это сообщение — email система работает!</p>
            <p><small>Auth System Test • {{ timestamp }}</small></p>
        </body></html>
        '''.replace('{{ timestamp }}', '2026-03-02')
        
        to_email = app.config.get('MAIL_RECIPIENT') or app.config.get('MAIL_DEFAULT_SENDER')
        
        success = send_email(
            to_email=to_email,
            subject='🧪 Тест email системы - Auth System',
            html_body=html_body,
            text_body='Тестовое письмо от Auth System'
        )
        
        if success:
            print(f"✅ Email sent to {to_email}")
            print("📬 Проверьте почтовый ящик!")
        else:
            print(f"❌ Failed to send email")
            print("🔍 Проверьте логи: tail -f logs/app.log | grep -i email")
        
        return success

if __name__ == '__main__':
    success = test_send_email()
    sys.exit(0 if success else 1)
