# app/api/admin_api.py
from flask import Blueprint, request, jsonify
from app import db, limiter
from app.models.user import User
from app.utils.email import send_verification_email

# Создаём blueprint если ещё не создан
admin_api_bp = Blueprint('admin_api', __name__, url_prefix='/api/admin')


@admin_api_bp.route('/users/<int:user_id>/resend-verification/', methods=['POST'])
@limiter.limit("10/minute")
def resend_user_verification(user_id):
    """API endpoint для повторной отправки верификации"""
    try:
        user = User.query.get_or_404(user_id)
        
        if user.is_verified:
            return jsonify({'message': 'Email already verified'}), 400
        
        if not user.can_resend_verification():
            return jsonify({'message': 'Please wait 5 minutes before resending'}), 429
        
        # Генерация нового токена
        user.generate_verification_token()
        
        # Отправка письма
        email_sent = send_verification_email(user)
        db.session.commit()
        
        return jsonify({
            'message': 'Verification email sent' if email_sent else 'Failed to send email',
            'email_sent': email_sent
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
