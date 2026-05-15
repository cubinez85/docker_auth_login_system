from flask import Blueprint, request, jsonify, g
from app import db
from app.decorators.permission import token_required

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/profile', methods=['GET'])
@token_required
def get_profile():
    user = g.current_user
    return jsonify({
        'id': user.id,
        'email': user.email,
        'last_name': user.last_name,
        'first_name': user.first_name,
        'middle_name': user.middle_name,
        'full_name': user.get_full_name(),
        'is_active': user.is_active,
        'created_at': user.created_at.isoformat() if user.created_at else None
    }), 200

@profile_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile():
    user = g.current_user
    data = request.get_json()
    
    # Update allowed fields
    allowed_fields = ['last_name', 'first_name', 'middle_name']
    
    for field in allowed_fields:
        if field in data:
            setattr(user, field, data[field])
    
    user.updated_at = db.func.now()
    db.session.commit()
    
    return jsonify({
        'message': 'Profile updated successfully',
        'user': {
            'id': user.id,
            'email': user.email,
            'last_name': user.last_name,
            'first_name': user.first_name,
            'middle_name': user.middle_name
        }
    }), 200

@profile_bp.route('/profile', methods=['DELETE'])
@token_required
def delete_profile():
    user = g.current_user
    
    # Soft delete
    user.soft_delete()
    db.session.commit()
    
    return jsonify({'message': 'Account deleted successfully'}), 200

@profile_bp.route('/logout', methods=['POST'])
@token_required
def logout():
    # In a real implementation, you might want to blacklist the token
    # For now, just return success (client should discard the token)
    return jsonify({'message': 'Logged out successfully'}), 200
