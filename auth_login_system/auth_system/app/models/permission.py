from app import db
from datetime import datetime

class Resource(db.Model):
    __tablename__ = 'resources'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # 'projects', 'documents', etc.
    description = db.Column(db.String(200))
    
    permissions = db.relationship('Permission', back_populates='resource')
    
    def __repr__(self):
        return f'<Resource {self.name}>'

class Action(db.Model):
    __tablename__ = 'actions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)  # 'create', 'read', 'update', 'delete'
    description = db.Column(db.String(200))
    
    permissions = db.relationship('Permission', back_populates='action')
    
    def __repr__(self):
        return f'<Action {self.name}>'

class Permission(db.Model):
    __tablename__ = 'permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resources.id'), nullable=False)
    action_id = db.Column(db.Integer, db.ForeignKey('actions.id'), nullable=False)
    
    # Relationships
    resource = db.relationship('Resource', back_populates='permissions')
    action = db.relationship('Action', back_populates='permissions')
    role_permissions = db.relationship('RolePermission', back_populates='permission')
    user_permissions = db.relationship('UserPermission', back_populates='permission')
    
    __table_args__ = (db.UniqueConstraint('resource_id', 'action_id', name='unique_permission'),)
    
    def __repr__(self):
        return f'<Permission {self.resource.name}:{self.action.name}>'

class Role(db.Model):
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    
    # Relationships
    user_roles = db.relationship('UserRole', back_populates='role')
    permissions = db.relationship('RolePermission', back_populates='role')
    
    def __repr__(self):
        return f'<Role {self.name}>'

class RolePermission(db.Model):
    __tablename__ = 'role_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id'), nullable=False)
    
    # Relationships
    role = db.relationship('Role', back_populates='permissions')
    permission = db.relationship('Permission', back_populates='role_permissions')
    
    __table_args__ = (db.UniqueConstraint('role_id', 'permission_id', name='unique_role_permission'),)

class UserRole(db.Model):
    __tablename__ = 'user_roles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='roles')
    role = db.relationship('Role', back_populates='user_roles')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'role_id', name='unique_user_role'),)

class UserPermission(db.Model):
    __tablename__ = 'user_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id'), nullable=False)
    granted = db.Column(db.Boolean, default=True)  # True - разрешено, False - запрещено
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='permissions')
    permission = db.relationship('Permission', back_populates='user_permissions')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'permission_id', name='unique_user_permission'),)
