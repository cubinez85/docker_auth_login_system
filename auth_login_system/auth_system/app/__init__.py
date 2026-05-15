# app/__init__.py
from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_admin import Admin
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import config
import logging
import os

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
limiter = Limiter(key_func=get_remote_address)

# Logging setup
def setup_logging(app):
    """Настройка логирования с учётом Docker"""
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper())
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    
    # Handlers
    handlers = []
    
    # В Docker пишем в stdout/stderr
    if app.config.get('RUNNING_IN_DOCKER', False) or not app.config.get('LOG_FILE'):
        handlers.append(logging.StreamHandler())
    else:
        # На хосте пишем в файл
        log_file = app.config.get('LOG_FILE', 'logs/app.log')
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
        handlers.append(logging.StreamHandler())  # Дублируем в консоль для docker logs
    
    for handler in handlers:
        handler.setLevel(log_level)
        handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.handlers = []
    for handler in handlers:
        logger.addHandler(handler)
    
    return logging.getLogger(__name__)


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Настройка логирования
    logger = setup_logging(app)

    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app)
    limiter.init_app(app)

    # ✅ Инициализируем admin только если не testing
    if not app.config.get('TESTING', False):
        from flask_admin import Admin
        from app.admin.views import MyAdminIndexView
        admin_instance = Admin(
            name='Auth System Admin',
            template_mode='bootstrap4',
            index_view=MyAdminIndexView(),
            url='/admin',
        )
        admin_instance.init_app(app)
        
        # Настраиваем admin views
        try:
            from app.admin.views import setup_admin
            setup_admin(admin_instance, db)
            logger.info("✅ Admin views configured")
        except ImportError as e:
            logger.warning(f"⚠️ Could not configure admin views: {e}")

    # Import models within app context
    with app.app_context():
        try:
            from app.models.user import User
            from app.models.permission import (
                Resource, Action, Permission,
                Role, RolePermission, UserRole, UserPermission
            )
            from app.models.token import TokenBlacklist
            logger.info("✅ Models imported successfully")
        except Exception as e:
            logger.error(f"❌ Error importing models: {e}")
            raise

    # Register blueprints
    try:
        from app.api.auth import auth_bp
        from app.api.profile import profile_bp
        from app.api.mock_resources import mock_bp
        from app.api.admin_api import admin_api_bp
        from app.api.main_routes import main_bp

        app.register_blueprint(main_bp)
        app.register_blueprint(auth_bp)
        app.register_blueprint(profile_bp)
        app.register_blueprint(mock_bp)
        app.register_blueprint(admin_api_bp)

        logger.info("✅ Blueprints registered successfully")

    except Exception as e:
        logger.error(f"❌ Error registering blueprints: {e}")
        raise

    # Context processor for admin templates
    if not app.config.get('TESTING', False):
        @app.context_processor
        def inject_counts():
            try:
                from app.admin.views import count_users, count_roles, count_permissions
                return dict(
                    count_users=count_users,
                    count_roles=count_roles,
                    count_permissions=count_permissions
                )
            except Exception:
                return dict(
                    count_users=lambda: 0,
                    count_roles=lambda: 0,
                    count_permissions=lambda: 0
                )

    # =====================================================================
    # ✅ Редиректы для обратной совместимости (ВНУТРИ create_app!)
    # =====================================================================
    
    @app.route('/admin/user/new/', methods=['GET'])
    def redirect_user_create():
        """🔄 Редирект со старого URL создания пользователя"""
        return redirect('/admin/user_create/')

    @app.route('/admin/<model>/new/', methods=['GET'])
    def redirect_admin_create(model):
        """🔄 Общий редирект для других моделей"""
        return redirect(f'/admin/{model}/')

    @app.route('/admin/user/')
    def redirect_user_list():
        return redirect('/admin/user_list/')

    @app.route('/admin/role/')
    def redirect_role_list():
        return redirect('/admin/role_list/')

    @app.route('/admin/resource/')
    def redirect_resource_list():
        return redirect('/admin/resource_list/')

    @app.route('/admin/action/')
    def redirect_action_list():
        return redirect('/admin/action_list/')

    @app.route('/admin/permission/')
    def redirect_permission_list():
        return redirect('/admin/permission_list/')

    @app.route('/admin/userrole/')
    def redirect_userrole_list():
        return redirect('/admin/userrole_list/')

    @app.route('/admin/rolepermission/')
    def redirect_rolepermission_list():
        return redirect('/admin/rolepermission_list/')

    @app.route('/admin/userpermission/')
    def redirect_userpermission_list():
        return redirect('/admin/userpermission_list/')

    # =====================================================================
    # Error handlers
    # =====================================================================
    
    @app.errorhandler(404)
    def not_found_error(error):
        return {'error': 'Not found', 'message': str(error)}, 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        logger.error(f"Internal server error: {error}", exc_info=True)
        
        if app.config.get('DEBUG', False):
            import traceback
            return {
                'error': 'Internal server error',
                'message': str(error),
                'traceback': traceback.format_exc()
            }, 500
        
        return {'error': 'Internal server error'}, 500

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return {'error': 'Rate limit exceeded', 'message': str(e.description)}, 429

    logger.info(f"🚀 Application created with config: {config_name}")
    
    # =====================================================================
    # Context processors для шаблонов Flask-Admin
    # =====================================================================
    @app.context_processor
    def inject_flask_admin_globals():
        """
        Делает глобальные переменные доступными во всех шаблонах.
        Необходимо для корректной работы наследования шаблонов Flask-Admin.
        """
        return {
            # Переменная требуется шаблоном flask_admin/templates/bootstrap4/admin/master.html
            'admin_base_template': 'admin/base.html',
        }

    logger.info(f"🚀 Application created with config: {config_name}")
    return app  # ← ВСЕ декораторы должны быть ДО этой строки!

    return app  
