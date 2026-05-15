from flask import Blueprint, request, jsonify, g
from app.decorators.permission import permission_required, token_required
from app import limiter

# ✅ ВАЖНО: url_prefix задаётся ЗДЕСЬ
mock_bp = Blueprint('mock', __name__, url_prefix='/api')

# Mock data
PROJECTS = [
    {'id': 1, 'name': 'Project Alpha', 'owner_id': 1, 'status': 'active'},
    {'id': 2, 'name': 'Project Beta', 'owner_id': 2, 'status': 'active'},
    {'id': 3, 'name': 'Project Gamma', 'owner_id': 1, 'status': 'archived'},
]

DOCUMENTS = [
    {'id': 1, 'title': 'Document 1', 'project_id': 1, 'content': '...'},
    {'id': 2, 'title': 'Document 2', 'project_id': 1, 'content': '...'},
    {'id': 3, 'title': 'Document 3', 'project_id': 2, 'content': '...'},
]

# --- Projects ---

@mock_bp.route('/projects/', methods=['GET'])
@token_required
@limiter.limit("30/minute")
def get_projects():
    """GET /api/projects/ — список проектов (все аутентифицированные)"""
    return jsonify({
        'projects': PROJECTS,
        'count': len(PROJECTS)
    }), 200

@mock_bp.route('/projects/', methods=['POST'])
@permission_required('projects', 'create')
@limiter.limit("10/minute")
def create_project():
    """POST /api/projects/ — создание (только Admin/Manager)"""
    data = request.get_json() or {}
    return jsonify({
        'message': 'Project created successfully',
        'project': {
            'id': len(PROJECTS) + 1,
            'name': data.get('name', 'New Project'),
            'owner_id': g.current_user.id,
            'status': 'planning'
        }
    }), 201

@mock_bp.route('/projects/<int:project_id>/', methods=['GET'])
@token_required
@limiter.limit("30/minute")
def get_project(project_id):
    """GET /api/projects/{id}/ — детали (Admin или владелец)"""
    project = next((p for p in PROJECTS if p['id'] == project_id), None)

    if not project:
        return jsonify({'message': 'Project not found'}), 404

    # Проверка: суперпользователь или владелец
    if not g.current_user.is_superuser and project['owner_id'] != g.current_user.id:
        from app.models.user import UserRole, Role
        admin_role = Role.query.filter_by(name='Admin').first()
        if admin_role:
            is_admin = UserRole.query.filter_by(
                user_id=g.current_user.id,
                role_id=admin_role.id
            ).first()
            if not is_admin:
                return jsonify({'message': 'Access denied'}), 403
    
    return jsonify({'project': project}), 200

@mock_bp.route('/projects/<int:project_id>/', methods=['PUT'])
@permission_required('projects', 'update')
@limiter.limit("10/minute")
def update_project(project_id):
    """PUT /api/projects/{id}/ — редактирование"""
    project = next((p for p in PROJECTS if p['id'] == project_id), None)
    if not project:
        return jsonify({'message': 'Project not found'}), 404

    data = request.get_json() or {}
    # ✅ ИСПРАВЛЕНО: добавлено "data:"
    for key in ['name', 'status']:
        if key in data:
            project[key] = data[key]
    
    return jsonify({
        'message': 'Project updated successfully',
        'project': project
    }), 200

@mock_bp.route('/projects/<int:project_id>/', methods=['DELETE'])
@permission_required('projects', 'delete')
@limiter.limit("5/minute")
def delete_project(project_id):
    """DELETE /api/projects/{id}/ — удаление (только Admin)"""
    global PROJECTS
    PROJECTS = [p for p in PROJECTS if p['id'] != project_id]
    return jsonify({'message': 'Project deleted successfully'}), 200

# --- Documents ---

@mock_bp.route('/documents/', methods=['GET'])
@token_required
@limiter.limit("30/minute")
def get_documents():
    """GET /api/documents/ — список документов"""
    return jsonify({
        'documents': DOCUMENTS,
        'count': len(DOCUMENTS)
    }), 200

# --- Reports (Admin only) ---

@mock_bp.route('/reports/', methods=['GET'])
@permission_required('reports', 'read')
@limiter.limit("10/minute")
def get_reports():
    """GET /api/reports/ — отчеты (только Admin)"""
    return jsonify({
        'reports': [
            {'id': 1, 'name': 'Annual Report 2026', 'type': 'annual'},
            {'id': 2, 'name': 'Monthly Report March 2026', 'type': 'monthly'}
        ],
        'count': 2
    }), 200

# --- Health check (public) ---

@mock_bp.route('/health/', methods=['GET'])
def health_check():
    """GET /api/health/ — публичная проверка"""
    from datetime import datetime
    return jsonify({
        'status': 'ok',
        'service': 'auth_system',
        'timestamp': datetime.utcnow().isoformat()
    }), 200
