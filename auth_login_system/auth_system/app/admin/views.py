"""
Admin Views для Auth System

Кастомные BaseView для надёжного CRUD во всех разделах
"""

from flask_admin.contrib.sqla import ModelView
from flask_admin import BaseView, AdminIndexView, expose
from flask import redirect, url_for, request, render_template, flash, session, current_app
from app.utils.email import send_verification_email, send_password_reset_email
from werkzeug.security import generate_password_hash
from app import db
from app.models.user import User
from app.models.permission import (
    Resource, Action, Permission, Role,
    RolePermission, UserRole, UserPermission
)
from app.models.token import TokenBlacklist
from app.utils.jwt_helper import generate_tokens, blacklist_token, get_token_expires
from app.utils.email import send_verification_email
import jwt
from datetime import datetime
from markupsafe import Markup

# =============================================================================
# Кастомная главная страница админки
# =============================================================================


class MyAdminIndexView(AdminIndexView):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('url', '/admin/')
        kwargs.setdefault('template', 'admin/index.html')  # ← Ваш файл
        kwargs.setdefault('name', 'Dashboard')
        super().__init__(*args, **kwargs)

    @expose('/')
    def index(self):
        # Передаём переменные, которые нужны шаблону
        from app.admin.views import count_users, count_roles, count_permissions, count_blacklisted_tokens
        
        return self.render('admin/index.html',
                          count_users=count_users,
                          count_roles=count_roles,
                          count_permissions=count_permissions,
                          count_blacklisted_tokens=count_blacklisted_tokens)

# =============================================================================
# Базовый безопасный View
# =============================================================================
class AdminSecureView(ModelView):
    """Базовый View для списков (только просмотр/удаление)"""
    
    page_size = 20
    can_set_page_size = True
    can_create = False  # Используем кастомные CreateView
    can_edit = True
    can_delete = True
    can_view_details = True
    column_display_pk = True
    
    def is_accessible(self):
        return True
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('admin.index'))


# =============================================================================
# 🔐 Custom User Views
# =============================================================================

class UserCreateView(BaseView):
    """Простая форма создания пользователя"""
    
    @expose('/', methods=['GET', 'POST'])
    def index(self):
        if request.method == 'POST':
            try:
                email = request.form.get('email', '').strip().lower()
                password = request.form.get('password', '')
                confirm_password = request.form.get('confirm_password', '')
                last_name = request.form.get('last_name', '').strip()
                first_name = request.form.get('first_name', '').strip()
                middle_name = request.form.get('middle_name', '').strip()
                is_superuser = request.form.get('is_superuser') == 'on'
                is_active = request.form.get('is_active') != 'off'
                
                if not email or not password or not last_name or not first_name:
                    flash('❌ Email, пароль, фамилия и имя обязательны', 'danger')
                    return redirect(url_for('.index'))
                
                if password != confirm_password:
                    flash('❌ Пароли не совпадают', 'danger')
                    return redirect(url_for('.index'))
                
                if len(password) < 8:
                    flash('❌ Пароль должен быть минимум 8 символов', 'warning')
                    return redirect(url_for('.index'))
                
                # 🔍 Проверяем существует ли пользователь
                existing_user = User.query.filter_by(email=email).first()
                
                if existing_user:
                    # ✅ Если пользователь был soft-deleted — удаляем его полностью
                    if not existing_user.is_active:
                        try:
                            # Импортируем модели здесь (или добавьте в начало файла)
                            from app.models.permission import UserRole, UserPermission
                            
                            # Удаляем связанные записи
                            UserRole.query.filter_by(user_id=existing_user.id).delete(synchronize_session=False)
                            UserPermission.query.filter_by(user_id=existing_user.id).delete(synchronize_session=False)
                            
                            # Удаляем самого пользователя
                            db.session.delete(existing_user)
                            db.session.commit()
                            flash(f'🗑️ Предыдущий неактивный аккаунт {email} удалён', 'info')
                        except Exception as e:
                            db.session.rollback()
                            flash(f'❌ Ошибка при очистке: {str(e)}', 'danger')
                            return redirect(url_for('.index'))
                    else:
                        # ❌ Если пользователь активен — нельзя создать дубликат
                        flash(f'⚠️ Email {email} уже зарегистрирован', 'warning')
                        return redirect(url_for('.index'))
                
                # Создание нового пользователя
                user = User(
                    email=email,
                    last_name=last_name,
                    first_name=first_name,
                    middle_name=middle_name if middle_name else None,
                    is_superuser=is_superuser,
                    is_active=is_active
                )
                user.password = password
                
                # Генерация токена верификации
                user.generate_verification_token(
                    expires_hours=current_app.config.get('EMAIL_VERIFICATION_EXPIRES_HOURS', 24)
                )
                
                db.session.add(user)
                db.session.commit()
                
                # Отправка письма с подтверждением
                from app.utils.email import send_verification_email
                email_sent = send_verification_email(user)
                
                flash(f'✅ Пользователь {email} создан (ID: {user.id})' + 
                      ('' if email_sent else ' ⚠️ Письмо не отправлено'), 
                      'success')
                return redirect(url_for('user_list.index_view'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Ошибка: {str(e)}', 'danger')
                return redirect(url_for('.index'))
        
        return self.render('admin/user_create_simple.html')

class UserListView(AdminSecureView):
    """Список пользователей с кнопками управления"""
    
    list_template = 'admin/user_list.html'
    
    # ✅ Колонки с кнопками действий
    column_list = ['id', 'email', 'last_name', 'first_name', 'is_verified', 'is_active', 'created_at', 'resend_btn', 'reset_password_btn', 'edit_btn']
    
    column_searchable_list = ['email', 'last_name', 'first_name']
    column_filters = ['is_active', 'is_verified', 'created_at']
    column_default_sort = ('created_at', True)
    
    # ✅ Отключаем стандартные кнопки (используем кастомные)
    can_create = False
    can_edit = False
    can_delete = True
    can_view_details = True
    
    form_excluded_columns = ['password_hash', 'roles', 'permissions', 'deleted_at', 'verification_token', 'reset_token']
    
    def get_query(self):
        return super().get_query().filter_by(is_active=True)
    
    def get_count_query(self):
        return super().get_count_query().filter_by(is_active=True)
    
    def delete_model(self, model):
        """Мягкое удаление пользователя"""
        try:
            model.soft_delete()
            db.session.commit()
            flash(f'✅ Пользователь {model.email} деактивирован', 'success')
            return True
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Ошибка: {str(e)}', 'danger')
            return False
    
    # ========================================================================
    # 🔘 КНОПКИ В ТАБЛИЦЕ (рендереры)
    # ========================================================================
    
    def _render_resend_btn(self, view, context, model, name):
        """Кнопка: Повторная отправка верификации"""
        from markupsafe import Markup
        if model.is_verified:
            return Markup('<span class="badge bg-success">✅</span>')
        
        # ✅ Указываем на внутренний метод .resend_verification_action
        return Markup(f'''
        <form action="{url_for('.resend_verification_action', user_id=model.id)}" 
              method="POST" style="display:inline;" onsubmit="return confirm('Отправить письмо с подтверждением на {model.email}?');">
            <button type="submit" class="btn btn-sm btn-outline-primary btn-xs" title="Отправить верификацию">
                📧
            </button>
        </form>
        ''')
    
    def _render_reset_password_btn(self, view, context, model, name):
        """Кнопка: Сброс пароля"""
        from markupsafe import Markup
        # ✅ Указываем на внутренний метод .reset_password_action
        return Markup(f'''
        <form action="{url_for('.reset_password_action', user_id=model.id)}" 
              method="POST" style="display:inline;" onsubmit="return confirm('Отправить письмо для СБРОСА ПАРОЛЯ пользователю {model.email}?');">
            <button type="submit" class="btn btn-sm btn-outline-danger btn-xs" title="Сбросить пароль">
                🔐
            </button>
        </form>
        ''')
    
    def _render_edit_btn(self, view, context, model, name):
        """Кнопка: Редактирование пользователя"""
        from markupsafe import Markup
        # ✅ Указываем на внутренний метод .edit_action
        return Markup(f'''
        <a href="{url_for('.edit_action', user_id=model.id)}" 
           class="btn btn-sm btn-outline-primary btn-xs"
           title="Редактировать пользователя">
            ✏️
        </a>
        ''')
    
    # ========================================================================
    # ⚙️ ДЕЙСТВИЯ (внутренние методы, не отображаются в меню)
    # ========================================================================
    
    @expose('/resend/<int:user_id>/', methods=['POST'])
    def resend_verification_action(self, user_id):
        """Действие: Повторная отправка верификации"""
        try:
            user = User.query.get_or_404(user_id)
            
            if user.is_verified:
                flash(f'⚠️ Email {user.email} уже подтверждён', 'warning')
                return redirect(url_for('.index_view'))
            
            user.generate_verification_token()
            email_sent = send_verification_email(user)
            db.session.commit()
            
            if email_sent:
                flash(f'✅ Письмо отправлено на {user.email}', 'success')
            else:
                flash(f'⚠️ Не удалось отправить письмо (проверьте логи)', 'warning')
                
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Ошибка: {str(e)}', 'danger')
            
        return redirect(url_for('.index_view'))
    
    @expose('/reset/<int:user_id>/', methods=['POST'])
    def reset_password_action(self, user_id):
        """Действие: Сброс пароля"""
        try:
            user = User.query.get_or_404(user_id)
            
            user.generate_password_reset_token()
            email_sent = send_password_reset_email(user)
            db.session.commit()
            
            if email_sent:
                flash(f'✅ Письмо для сброса пароля отправлено на {user.email}', 'success')
            else:
                flash(f'⚠️ Не удалось отправить письмо (проверьте логи)', 'warning')
                
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Ошибка: {str(e)}', 'danger')
            
        return redirect(url_for('.index_view'))
    
    @expose('/edit/<int:user_id>/', methods=['GET', 'POST'])
    def edit_action(self, user_id):
        """Действие: Редактирование пользователя (кастомная форма)"""
        user = User.query.get_or_404(user_id)
        
        if request.method == 'POST':
            try:
                # Обновление полей (email нельзя менять)
                user.last_name = request.form.get('last_name', '').strip()
                user.first_name = request.form.get('first_name', '').strip()
                user.middle_name = request.form.get('middle_name', '').strip() or None
                user.is_active = request.form.get('is_active') == 'on'
                user.is_superuser = request.form.get('is_superuser') == 'on'
                
                # Если введён новый пароль — хешируем и сохраняем
                new_password = request.form.get('password', '').strip()
                if new_password:
                    # Валидация пароля
                    if len(new_password) < 8:
                        flash('❌ Пароль должен быть минимум 8 символов', 'warning')
                        return self.render('admin/user_edit.html', user=user)
                    
                    if not re.search(r'[A-Z]', new_password):
                        flash('❌ Пароль должен содержать заглавную букву', 'warning')
                        return self.render('admin/user_edit.html', user=user)
                    
                    if not re.search(r'[a-z]', new_password):
                        flash('❌ Пароль должен содержать строчную букву', 'warning')
                        return self.render('admin/user_edit.html', user=user)
                    
                    if not re.search(r'\d', new_password):
                        flash('❌ Пароль должен содержать цифру', 'warning')
                        return self.render('admin/user_edit.html', user=user)
                    
                    user.password = new_password  # Хеширование через property
                
                db.session.commit()
                flash(f'✅ Пользователь {user.email} обновлён', 'success')
                return redirect(url_for('.index_view'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Ошибка: {str(e)}', 'danger')
        
        # GET: показываем форму редактирования
        return self.render('admin/user_edit.html', user=user)
    
    # ========================================================================
    # ИНИЦИАЛИЗАЦИЯ
    # ========================================================================
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # ✅ Регистрируем форматтеры колонок
        self.column_formatters = {
            'is_verified': lambda v, c, m, p: '✅' if m.is_verified else '⏳',
            'is_active': lambda v, c, m, p: '🟢' if m.is_active else '🔴',
            'resend_btn': self._render_resend_btn,
            'reset_password_btn': self._render_reset_password_btn,
            'edit_btn': self._render_edit_btn,
        }

# =============================================================================
# 🎭 Custom Role Views
# =============================================================================

class RoleCreateView(BaseView):
    """Простая форма создания роли"""
    
    @expose('/', methods=['GET', 'POST'])
    def index(self):
        if request.method == 'POST':
            try:
                name = request.form.get('name', '').strip()
                description = request.form.get('description', '').strip()
                
                if not name:
                    flash('❌ Название роли обязательно', 'danger')
                    return redirect(url_for('.index'))
                
                if Role.query.filter_by(name=name).first():
                    flash(f'⚠️ Роль "{name}" уже существует', 'warning')
                    return redirect(url_for('.index'))
                
                role = Role(name=name, description=description if description else None)
                db.session.add(role)
                db.session.commit()
                
                flash(f'✅ Роль "{name}" создана (ID: {role.id})', 'success')
                return redirect(url_for('role_list.index_view'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Ошибка: {str(e)}', 'danger')
                return redirect(url_for('.index'))
        
        return self.render('admin/role_create_simple.html')


class RoleListView(AdminSecureView):
    """Список ролей"""

    can_create = False
    can_edit = False

    column_list = ['id', 'name', 'description']
    column_searchable_list = ['name']
    column_filters = ['name']
    
    def delete_model(self, model):
        # Проверка на связанные записи
        if model.user_roles or model.permissions:
            flash(f'⚠️ Нельзя удалить роль "{model.name}": есть связанные записи', 'warning')
            return False
        return super().delete_model(model)


# =============================================================================
# 📦 Custom Resource Views
# =============================================================================

class ResourceCreateView(BaseView):
    """Простая форма создания ресурса"""
    
    @expose('/', methods=['GET', 'POST'])
    def index(self):
        if request.method == 'POST':
            try:
                name = request.form.get('name', '').strip().lower()
                description = request.form.get('description', '').strip()
                
                if not name:
                    flash('❌ Название ресурса обязательно', 'danger')
                    return redirect(url_for('.index'))
                
                if Resource.query.filter_by(name=name).first():
                    flash(f'⚠️ Ресурс "{name}" уже существует', 'warning')
                    return redirect(url_for('.index'))
                
                resource = Resource(name=name, description=description if description else None)
                db.session.add(resource)
                db.session.commit()
                
                flash(f'✅ Ресурс "{name}" создан (ID: {resource.id})', 'success')
                return redirect(url_for('resource_list.index_view'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Ошибка: {str(e)}', 'danger')
                return redirect(url_for('.index'))
        
        return self.render('admin/resource_create_simple.html')


class ResourceListView(AdminSecureView):
    """Список ресурсов"""

    can_create = False
    can_edit = False

    column_list = ['id', 'name', 'description']
    column_searchable_list = ['name']
    column_filters = ['name']
    
    def delete_model(self, model):
        if model.permissions:
            flash(f'⚠️ Нельзя удалить ресурс "{model.name}": есть связанные разрешения', 'warning')
            return False
        return super().delete_model(model)


# =============================================================================
# ⚡ Custom Action Views
# =============================================================================

class ActionCreateView(BaseView):
    """Простая форма создания действия"""
    
    @expose('/', methods=['GET', 'POST'])
    def index(self):
        if request.method == 'POST':
            try:
                name = request.form.get('name', '').strip().lower()
                description = request.form.get('description', '').strip()
                
                if not name:
                    flash('❌ Название действия обязательно', 'danger')
                    return redirect(url_for('.index'))
                
                if Action.query.filter_by(name=name).first():
                    flash(f'⚠️ Действие "{name}" уже существует', 'warning')
                    return redirect(url_for('.index'))
                
                action = Action(name=name, description=description if description else None)
                db.session.add(action)
                db.session.commit()
                
                flash(f'✅ Действие "{name}" создано (ID: {action.id})', 'success')
                return redirect(url_for('action_list.index_view'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Ошибка: {str(e)}', 'danger')
                return redirect(url_for('.index'))
        
        return self.render('admin/action_create_simple.html')


class ActionListView(AdminSecureView):
    """Список действий"""
    
    column_list = ['id', 'name', 'description']
    column_searchable_list = ['name']
    column_filters = ['name']
    
    def delete_model(self, model):
        if model.permissions:
            flash(f'⚠️ Нельзя удалить действие "{model.name}": есть связанные разрешения', 'warning')
            return False
        return super().delete_model(model)


# =============================================================================
# 🔑 Custom Permission Views
# =============================================================================

class PermissionCreateView(BaseView):
    """Простая форма создания разрешения (Resource + Action)"""
    
    @expose('/', methods=['GET', 'POST'])
    def index(self):
        if request.method == 'POST':
            try:
                resource_id = request.form.get('resource_id', type=int)
                action_id = request.form.get('action_id', type=int)
                
                if not resource_id or not action_id:
                    flash('❌ Ресурс и действие обязательны', 'danger')
                    return redirect(url_for('.index'))
                
                # Проверка на дубликат
                existing = Permission.query.filter_by(
                    resource_id=resource_id,
                    action_id=action_id
                ).first()
                
                if existing:
                    flash('⚠️ Такое разрешение уже существует', 'warning')
                    return redirect(url_for('.index'))
                
                permission = Permission(resource_id=resource_id, action_id=action_id)
                db.session.add(permission)
                db.session.commit()
                
                resource = Resource.query.get(resource_id)
                action = Action.query.get(action_id)
                flash(f'✅ Разрешение {resource.name}:{action.name} создано (ID: {permission.id})', 'success')
                return redirect(url_for('permission_list.index_view'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Ошибка: {str(e)}', 'danger')
                return redirect(url_for('.index'))
        
        resources = Resource.query.order_by(Resource.name).all()
        actions = Action.query.order_by(Action.name).all()
        return self.render('admin/permission_create_simple.html', resources=resources, actions=actions)


class PermissionListView(AdminSecureView):
    """Список разрешений"""

    can_create = False
    can_edit = False

    column_list = ['id', 'resource', 'action']
    column_filters = ['resource_id', 'action_id']
    
    def delete_model(self, model):
        if model.role_permissions or model.user_permissions:
            flash('⚠️ Нельзя удалить разрешение: есть связанные назначения', 'warning')
            return False
        return super().delete_model(model)


# =============================================================================
# 👤→🎭 Custom UserRole Views
# =============================================================================

class UserRoleCreateView(BaseView):
    """Простая форма назначения роли пользователю"""
    
    @expose('/', methods=['GET', 'POST'])
    def index(self):
        if request.method == 'POST':
            try:
                user_id = request.form.get('user_id', type=int)
                role_id = request.form.get('role_id', type=int)
                
                if not user_id or not role_id:
                    flash('❌ Пользователь и роль обязательны', 'danger')
                    return redirect(url_for('.index'))
                
                # Проверка на дубликат
                existing = UserRole.query.filter_by(user_id=user_id, role_id=role_id).first()
                if existing:
                    flash('⚠️ Эта роль уже назначена пользователю', 'warning')
                    return redirect(url_for('.index'))
                
                user_role = UserRole(user_id=user_id, role_id=role_id)
                db.session.add(user_role)
                db.session.commit()
                
                user = User.query.get(user_id)
                role = Role.query.get(role_id)
                flash(f'✅ Роль "{role.name}" назначена пользователю {user.email}', 'success')
                return redirect(url_for('userrole_list.index_view'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Ошибка: {str(e)}', 'danger')
                return redirect(url_for('.index'))
        
        users = User.query.filter_by(is_active=True).order_by(User.email).all()
        roles = Role.query.order_by(Role.name).all()
        return self.render('admin/userrole_create_simple.html', users=users, roles=roles)


class UserRoleListView(AdminSecureView):
    """Список назначений ролей"""

    can_create = False
    can_edit = False

    column_list = ['id', 'user', 'role', 'assigned_at']
    column_filters = ['user_id', 'role_id']
    column_default_sort = ('assigned_at', True)


# =============================================================================
# 🎭→🔑 Custom RolePermission Views
# =============================================================================

class RolePermissionCreateView(BaseView):
    """Простая форма назначения разрешения роли"""
    
    @expose('/', methods=['GET', 'POST'])
    def index(self):
        if request.method == 'POST':
            try:
                role_id = request.form.get('role_id', type=int)
                permission_id = request.form.get('permission_id', type=int)
                
                if not role_id or not permission_id:
                    flash('❌ Роль и разрешение обязательны', 'danger')
                    return redirect(url_for('.index'))
                
                # Проверка на дубликат
                existing = RolePermission.query.filter_by(role_id=role_id, permission_id=permission_id).first()
                if existing:
                    flash('⚠️ Это разрешение уже назначено роли', 'warning')
                    return redirect(url_for('.index'))
                
                role_perm = RolePermission(role_id=role_id, permission_id=permission_id)
                db.session.add(role_perm)
                db.session.commit()
                
                role = Role.query.get(role_id)
                perm = Permission.query.get(permission_id)
                flash(f'✅ Разрешение {perm.resource.name}:{perm.action.name} назначено роли "{role.name}"', 'success')
                return redirect(url_for('rolepermission_list.index_view'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Ошибка: {str(e)}', 'danger')
                return redirect(url_for('.index'))
        
        roles = Role.query.order_by(Role.name).all()
        permissions = Permission.query.join(Resource).join(Action).order_by(Resource.name, Action.name).all()
        return self.render('admin/rolepermission_create_simple.html', roles=roles, permissions=permissions)


class RolePermissionListView(AdminSecureView):

    """Список назначений разрешений ролям"""
    can_create = False
    can_edit = False

    column_list = ['id', 'role', 'permission']
    column_filters = ['role_id', 'permission_id']


# =============================================================================
# 👤→🔑 Custom UserPermission Views
# =============================================================================

class UserPermissionCreateView(BaseView):
    """Простая форма назначения индивидуального разрешения пользователю"""
    
    @expose('/', methods=['GET', 'POST'])
    def index(self):
        if request.method == 'POST':
            try:
                user_id = request.form.get('user_id', type=int)
                permission_id = request.form.get('permission_id', type=int)
                granted = request.form.get('granted') == 'on'
                
                if not user_id or not permission_id:
                    flash('❌ Пользователь и разрешение обязательны', 'danger')
                    return redirect(url_for('.index'))
                
                # Проверка на дубликат
                existing = UserPermission.query.filter_by(user_id=user_id, permission_id=permission_id).first()
                if existing:
                    flash('⚠️ Это разрешение уже назначено пользователю', 'warning')
                    return redirect(url_for('.index'))
                
                user_perm = UserPermission(user_id=user_id, permission_id=permission_id, granted=granted)
                db.session.add(user_perm)
                db.session.commit()
                
                user = User.query.get(user_id)
                perm = Permission.query.get(permission_id)
                action = 'разрешено' if granted else 'запрещено'
                flash(f'✅ Доступ {perm.resource.name}:{perm.action.name} {action} пользователю {user.email}', 'success')
                return redirect(url_for('userpermission_list.index_view'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Ошибка: {str(e)}', 'danger')
                return redirect(url_for('.index'))
        
        users = User.query.filter_by(is_active=True).order_by(User.email).all()
        permissions = Permission.query.join(Resource).join(Action).order_by(Resource.name, Action.name).all()
        return self.render('admin/userpermission_create_simple.html', users=users, permissions=permissions)


class UserPermissionListView(AdminSecureView):
    """Список индивидуальных разрешений пользователей"""

    can_create = False
    can_edit = False

    column_list = ['id', 'user', 'permission', 'granted', 'assigned_at']
    column_filters = ['user_id', 'permission_id', 'granted']


# =============================================================================
# Функция настройки админки
# =============================================================================
def setup_admin(admin_instance, db_instance):
    """Регистрация всех admin views"""
    
    # === User Management ===
    admin_instance.add_view(UserCreateView(
        name='➕ Create User',
        category='👤 User Management',
        endpoint='user_create'
    ))
    admin_instance.add_view(UserListView(
        User, db_instance.session,
        name='👥 Users',
        category='👤 User Management',
        endpoint='user_list'
    ))

    # === Access Control: Roles ===
    admin_instance.add_view(RoleCreateView(
        name='➕ Create Role',
        category='🔐 Access Control',
        endpoint='role_create'
    ))
    admin_instance.add_view(RoleListView(
        Role, db_instance.session,
        name='🎭 Roles',
        category='🔐 Access Control',
        endpoint='role_list'
    ))
    
    # === Access Control: Resources ===
    admin_instance.add_view(ResourceCreateView(
        name='➕ Create Resource',
        category='🔐 Access Control',
        endpoint='resource_create'
    ))
    admin_instance.add_view(ResourceListView(
        Resource, db_instance.session,
        name='📦 Resources',
        category='🔐 Access Control',
        endpoint='resource_list'
    ))
    
    # === Access Control: Actions ===
    admin_instance.add_view(ActionCreateView(
        name='➕ Create Action',
        category='🔐 Access Control',
        endpoint='action_create'
    ))
    admin_instance.add_view(ActionListView(
        Action, db_instance.session,
        name='⚡ Actions',
        category='🔐 Access Control',
        endpoint='action_list'
    ))
    
    # === Access Control: Permissions ===
    admin_instance.add_view(PermissionCreateView(
        name='➕ Create Permission',
        category='🔐 Access Control',
        endpoint='permission_create'
    ))
    admin_instance.add_view(PermissionListView(
        Permission, db_instance.session,
        name='🔑 Permissions',
        category='🔐 Access Control',
        endpoint='permission_list'
    ))
    
    # === Access Control: User Roles ===
    admin_instance.add_view(UserRoleCreateView(
        name='➕ Assign Role to User',
        category='🔐 Access Control',
        endpoint='userrole_create'
    ))
    admin_instance.add_view(UserRoleListView(
        UserRole, db_instance.session,
        name='👤→🎭 User Roles',
        category='🔐 Access Control',
        endpoint='userrole_list'
    ))
    
    # === Access Control: Role Permissions ===
    admin_instance.add_view(RolePermissionCreateView(
        name='➕ Assign Permission to Role',
        category='🔐 Access Control',
        endpoint='rolepermission_create'
    ))
    admin_instance.add_view(RolePermissionListView(
        RolePermission, db_instance.session,
        name='🎭→🔑 Role Permissions',
        category='🔐 Access Control',
        endpoint='rolepermission_list'
    ))
    
    # === Access Control: User Permissions ===
    admin_instance.add_view(UserPermissionCreateView(
        name='➕ Assign Permission to User',
        category='🔐 Access Control',
        endpoint='userpermission_create'
    ))
    admin_instance.add_view(UserPermissionListView(
        UserPermission, db_instance.session,
        name='👤→🔑 User Permissions',
        category='🔐 Access Control',
        endpoint='userpermission_list'
    ))
    
    print("✅ Admin views configured successfully")
    return admin_instance


# Для обратной совместимости
add_admin_views = setup_admin


# =============================================================================
# Helper функции для шаблонов
# =============================================================================
def count_users():
    try:
        return User.query.filter_by(is_active=True).count()
    except:
        return 0

def count_roles():
    try:
        return Role.query.count()
    except:
        return 0

def count_permissions():
    try:
        return Permission.query.count()
    except:
        return 0

def count_blacklisted_tokens():
    try:
        return TokenBlacklist.query.filter(
            TokenBlacklist.expires_at > datetime.utcnow()
        ).count()
    except:
        return 0
