from flask import Blueprint, request, jsonify
from models import User, db
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import check_password_hash, generate_password_hash  # <- IMPORTANTE

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
@auth_bp.route('/portal-carlos', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        token = create_access_token(identity=str(user.id))  # JWT necesita string
        return jsonify({"token": token}), 200
    return jsonify({"error": "Credenciales inválidas"}), 401

@auth_bp.route('/change-password', methods=['PUT'])
@jwt_required()
def change_password():
    print("Endpoint /auth/change-password llamado")
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    data = request.json

    if not data.get('current_password') or not data.get('new_password'):
        return jsonify({"error": "Se requieren la contraseña actual y la nueva"}), 400

    # Verificar usando werkzeug, NO bcrypt
    if not check_password_hash(user.password, data['current_password']):
        return jsonify({"error": "La contraseña actual es incorrecta"}), 401

    # Hashear nueva contraseña usando werkzeug
    user.password = generate_password_hash(data['new_password'])
    db.session.commit()

    return jsonify({"message": "Contraseña actualizada exitosamente"}), 200
