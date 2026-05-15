#!/usr/bin/env python3
"""
Script to seed the database with initial data
"""
import sys
import os
from datetime import datetime

# Добавляем путь к проекту в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from app import create_app, db
    from app.models.user import User
    from app.models.permission import Resource, Action, Permission, Role, RolePermission, UserRole
    from werkzeug.security import generate_password_hash
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this script from the project root directory")
    sys.exit(1)

def seed_data():
    """Main seeding function"""
    app = create_app('production')
    
    with app.app_context():
        print("Starting database seeding...")
        
        # 1. Создание действий (Actions)
        print("\n1. Creating actions...")
        actions_data = [
            {'name': 'create', 'description': 'Create new resources'},
            {'name': 'read', 'description': 'Read resources'},
            {'name': 'update', 'description': 'Update existing resources'},
            {'name': 'delete', 'description': 'Delete resources'},
        ]
        
        actions = {}
        for action_data in actions_data:
            action = Action.query.filter_by(name=action_data['name']).first()
            if not action:
                action = Action(**action_data)
                db.session.add(action)
                print(f"  - Created action: {action_data['name']}")
            else:
                print(f"  - Action already exists: {action_data['name']}")
            actions[action_data['name']] = action
        
        db.session.flush()
        
        # 2. Создание ресурсов (Resources)
        print("\n2. Creating resources...")
        resources_data = [
            {'name': 'projects', 'description': 'Project management'},
            {'name': 'documents', 'description': 'Document management'},
            {'name': 'reports', 'description': 'Reports and analytics'},
            {'name': 'users', 'description': 'User management'},
        ]
        
        resources = {}
        for resource_data in resources_data:
            resource = Resource.query.filter_by(name=resource_data['name']).first()
            if not resource:
                resource = Resource(**resource_data)
                db.session.add(resource)
                print(f"  - Created resource: {resource_data['name']}")
            else:
                print(f"  - Resource already exists: {resource_data['name']}")
            resources[resource_data['name']] = resource
        
        db.session.flush()
        
        # 3. Создание разрешений (Permissions)
        print("\n3. Creating permissions...")
        for resource_name, resource in resources.items():
            for action_name, action in actions.items():
                permission = Permission.query.filter_by(
                    resource_id=resource.id,
                    action_id=action.id
                ).first()
                if not permission:
                    permission = Permission(
                        resource_id=resource.id,
                        action_id=action.id
                    )
                    db.session.add(permission)
                    print(f"  - Created permission: {resource_name}:{action_name}")
        
        db.session.flush()
        
        # 4. Создание ролей (Roles)
        print("\n4. Creating roles...")
        roles_data = [
            {'name': 'Admin', 'description': 'Full system access'},
            {'name': 'Manager', 'description': 'Can manage projects and documents'},
            {'name': 'User', 'description': 'Regular user with basic access'},
        ]
        
        roles = {}
        for role_data in roles_data:
            role = Role.query.filter_by(name=role_data['name']).first()
            if not role:
                role = Role(**role_data)
                db.session.add(role)
                print(f"  - Created role: {role_data['name']}")
            else:
                print(f"  - Role already exists: {role_data['name']}")
            roles[role_data['name']] = role
        
        db.session.flush()
        
        # 5. Назначение разрешений ролям
        print("\n5. Assigning permissions to roles...")
        
        # Admin получает все разрешения
        admin_role = roles.get('Admin')
        if admin_role:
            all_permissions = Permission.query.all()
            for permission in all_permissions:
                rp = RolePermission.query.filter_by(
                    role_id=admin_role.id,
                    permission_id=permission.id
                ).first()
                if not rp:
                    rp = RolePermission(
                        role_id=admin_role.id,
                        permission_id=permission.id
                    )
                    db.session.add(rp)
            print(f"  - Assigned {len(all_permissions)} permissions to Admin role")
        
        # Manager получает разрешения на projects и documents (create, read, update)
        manager_role = roles.get('Manager')
        if manager_role:
            manager_permissions_count = 0
            for resource_name in ['projects', 'documents']:
                resource = resources.get(resource_name)
                if resource:
                    for action_name in ['create', 'read', 'update']:
                        action = actions.get(action_name)
                        if action:
                            permission = Permission.query.filter_by(
                                resource_id=resource.id,
                                action_id=action.id
                            ).first()
                            if permission:
                                rp = RolePermission.query.filter_by(
                                    role_id=manager_role.id,
                                    permission_id=permission.id
                                ).first()
                                if not rp:
                                    rp = RolePermission(
                                        role_id=manager_role.id,
                                        permission_id=permission.id
                                    )
                                    db.session.add(rp)
                                    manager_permissions_count += 1
            print(f"  - Assigned {manager_permissions_count} permissions to Manager role")
        
        # User получает только read разрешения
        user_role = roles.get('User')
        if user_role:
            user_permissions_count = 0
            for resource_name in ['projects', 'documents']:
                resource = resources.get(resource_name)
                if resource:
                    action = actions.get('read')
                    if action:
                        permission = Permission.query.filter_by(
                            resource_id=resource.id,
                            action_id=action.id
                        ).first()
                        if permission:
                            rp = RolePermission.query.filter_by(
                                role_id=user_role.id,
                                permission_id=permission.id
                            ).first()
                            if not rp:
                                rp = RolePermission(
                                    role_id=user_role.id,
                                    permission_id=permission.id
                                )
                                db.session.add(rp)
                                user_permissions_count += 1
            print(f"  - Assigned {user_permissions_count} permissions to User role")
        
        db.session.flush()
        
        # 6. Создание тестовых пользователей
        print("\n6. Creating test users...")
        users_data = [
            {
                'email': 'admin@example.com',
                'password': 'Admin123!',
                'last_name': 'Admin',
                'first_name': 'System',
                'is_superuser': True
            },
            {
                'email': 'manager@example.com',
                'password': 'Manager123!',
                'last_name': 'Manager',
                'first_name': 'Project',
            },
            {
                'email': 'user1@example.com',
                'password': 'User123!',
                'last_name': 'User',
                'first_name': 'Regular',
            },
            {
                'email': 'user2@example.com',
                'password': 'User123!',
                'last_name': 'Smith',
                'first_name': 'John',
                'middle_name': 'Doe'
            },
        ]
        
        created_users = []
        for user_data in users_data:
            user = User.query.filter_by(email=user_data['email']).first()
            if not user:
                user = User(
                    email=user_data['email'],
                    last_name=user_data['last_name'],
                    first_name=user_data['first_name'],
                    middle_name=user_data.get('middle_name', ''),
                    is_superuser=user_data.get('is_superuser', False)
                )
                user.password = user_data['password']
                db.session.add(user)
                db.session.flush()
                created_users.append(user)
                print(f"  - Created user: {user_data['email']}")
            else:
                print(f"  - User already exists: {user_data['email']}")
                created_users.append(user)
        
        db.session.flush()
        
        # 7. Назначение ролей пользователям
        print("\n7. Assigning roles to users...")
        
        for user in created_users:
            if user.email == 'admin@example.com':
                # Admin уже superuser, роль не требуется
                print(f"  - {user.email}: superuser (no role needed)")
                
            elif user.email == 'manager@example.com':
                role = roles.get('Manager')
                if role:
                    ur = UserRole.query.filter_by(
                        user_id=user.id,
                        role_id=role.id
                    ).first()
                    if not ur:
                        ur = UserRole(user_id=user.id, role_id=role.id)
                        db.session.add(ur)
                        print(f"  - {user.email}: assigned Manager role")
                else:
                    print(f"  - Warning: Manager role not found")
                    
            else:  # regular users
                role = roles.get('User')
                if role:
                    ur = UserRole.query.filter_by(
                        user_id=user.id,
                        role_id=role.id
                    ).first()
                    if not ur:
                        ur = UserRole(user_id=user.id, role_id=role.id)
                        db.session.add(ur)
                        print(f"  - {user.email}: assigned User role")
                else:
                    print(f"  - Warning: User role not found")
        
        # Сохраняем все изменения
        db.session.commit()
        
        print("\n" + "="*50)
        print("✅ Database seeding completed successfully!")
        print("="*50)
        
        # Вывод статистики
        print("\nDatabase statistics:")
        print(f"  - Users: {User.query.count()}")
        print(f"  - Roles: {Role.query.count()}")
        print(f"  - Resources: {Resource.query.count()}")
        print(f"  - Actions: {Action.query.count()}")
        print(f"  - Permissions: {Permission.query.count()}")
        print(f"  - RolePermissions: {RolePermission.query.count()}")
        print(f"  - UserRoles: {UserRole.query.count()}")
        
        print("\nTest users credentials:")
        print("  - admin@example.com / Admin123! (superuser)")
        print("  - manager@example.com / Manager123! (Manager role)")
        print("  - user1@example.com / User123! (User role)")
        print("  - user2@example.com / User123! (User role)")
        
        return True

if __name__ == '__main__':
    print("Starting seeding process...")
    success = seed_data()
    if success:
        print("\nSeeding completed. You can now use the application.")
    else:
        print("\nSeeding failed. Check the errors above.")
        sys.exit(1)
