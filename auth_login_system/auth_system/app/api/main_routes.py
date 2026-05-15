from flask import Blueprint, jsonify

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return jsonify({
        'message': 'Auth System API',
        'version': '1.0',
        'endpoints': {
            'auth': '/api/auth/',
            'admin': '/admin/',
            'api_docs': '/api/'
        }
    })

@main_bp.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'auth_system'})
