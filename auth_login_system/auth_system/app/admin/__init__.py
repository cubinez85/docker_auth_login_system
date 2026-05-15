"""
Admin package for Auth System

Инициализация Flask-Admin панели управления
"""

from flask_admin import Admin, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask import redirect, url_for

# =============================================================================
# Импорт view классов из views.py
# =============================================================================
from app.admin.views import (
    # Основные функции
    setup_admin,
    add_admin_views,
    
    # Базовые классы
    MyAdminIndexView,
    AdminSecureView,
    
    # User Management
    UserCreateView,
    UserListView,
    
    # Role Management
    RoleCreateView,
    RoleListView,
    
    # Resource Management
    ResourceCreateView,
    ResourceListView,
    
    # Action Management
    ActionCreateView,
    ActionListView,
    
    # Permission Management
    PermissionCreateView,
    PermissionListView,
    
    # UserRole Management
    UserRoleCreateView,
    UserRoleListView,
    
    # RolePermission Management
    RolePermissionCreateView,
    RolePermissionListView,
    
    # UserPermission Management
    UserPermissionCreateView,
    UserPermissionListView,
    
    # Helper функции для шаблонов
    count_users,
    count_roles,
    count_permissions,
    count_blacklisted_tokens,
)

# =============================================================================
# Публичный API пакета
# =============================================================================
__all__ = [
    # Функции инициализации
    'setup_admin',
    'add_admin_views',
    
    # Базовые классы Flask-Admin
    'Admin',
    'ModelView',
    'BaseView',
    'expose',
    
    # Custom View классы
    'MyAdminIndexView',
    'AdminSecureView',
    'UserCreateView',
    'UserListView',
    'RoleCreateView',
    'RoleListView',
    'ResourceCreateView',
    'ResourceListView',
    'ActionCreateView',
    'ActionListView',
    'PermissionCreateView',
    'PermissionListView',
    'UserRoleCreateView',
    'UserRoleListView',
    'RolePermissionCreateView',
    'RolePermissionListView',
    'UserPermissionCreateView',
    'UserPermissionListView',
    
    # Helper функции для шаблонов
    'count_users',
    'count_roles',
    'count_permissions',
    'count_blacklisted_tokens',
]


# =============================================================================
# Альтернативная функция инициализации
# =============================================================================
def init_admin(app, db, admin_instance=None):
    """
    Инициализация админ-панели с приложением Flask
    """
    if admin_instance is None:
        admin_instance = Admin(
            app,
            name='Auth System Admin',
            template_mode='bootstrap4',
            index_view=MyAdminIndexView(
                template='admin/index.html',
                name='Dashboard',
                url='/admin/'
            ),
            base_template='admin/master.html'
        )
    
    # Настройка view
    setup_admin(admin_instance, db)
    
    return admin_instance


# =============================================================================
# Регистрация context processors
# =============================================================================
def register_context_processors(app):
    """Регистрация helper функций как context processors"""
    
    @app.context_processor
    def inject_admin_counts():
        """Добавляет счётки в контекст всех шаблонов"""
        try:
            return dict(
                count_users=count_users,
                count_roles=count_roles,
                count_permissions=count_permissions,
                count_blacklisted_tokens=count_blacklisted_tokens,
            )
        except Exception as e:
            return dict(
                count_users=lambda: 0,
                count_roles=lambda: 0,
                count_permissions=lambda: 0,
                count_blacklisted_tokens=lambda: 0,
            )
    
    return app
