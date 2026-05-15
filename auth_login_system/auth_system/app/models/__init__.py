# Импорт моделей
from .user import User
from .permission import (
    Resource,
    Action, 
    Permission,
    Role,
    RolePermission,
    UserRole,
    UserPermission
)

# Импорт TokenBlacklist (создайте этот файл, если его нет)
try:
    from .token import TokenBlacklist
except ImportError:
    TokenBlacklist = None

__all__ = [
    'User',
    'TokenBlacklist',
    'Resource',
    'Action',
    'Permission', 
    'Role',
    'RolePermission',
    'UserRole',
    'UserPermission'
]
