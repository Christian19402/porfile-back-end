from flask import Blueprint, request, jsonify, send_from_directory, current_app
from models import User, CV, db
from flask_jwt_extended import jwt_required, get_jwt_identity
import os

cv_bp = Blueprint('cv', __name__)

# ---------------- helpers de rutas ----------------
def uploads_root():
    # Preferimos la config; si no existe, fallback a ./uploads
    return current_app.config.get("UPLOADS_DIR", os.path.join(current_app.root_path, "uploads"))

def cv_dir():
    # Subcarpeta de CVs
    return current_app.config.get("CV_DIR", os.path.join(uploads_root(), "cvs"))

def rel_url_for(filename: str) -> str:
    # lo que guarda/expone el frontend
    return f"/uploads/cvs/{filename}"

def abs_path_from_rel(rel: str) -> str:
    # convierte "/uploads/cvs/xxx.pdf" -> <ABS>/cvs/xxx.pdf
    assert rel.startswith("/uploads/"), "se esperaba ruta /uploads/..."
    return os.path.join(uploads_root(), rel.replace("/uploads/", ""))

# ---------------- endpoints ----------------

@cv_bp.route('/', methods=['POST'])
@jwt_required()
def upload_cv():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "Invalid file type. Solo PDF"}), 400

    # asegurar carpeta
    os.makedirs(cv_dir(), exist_ok=True)

    # si ya hay CV, lo borramos (físico + BD)
    existing = CV.query.filter_by(user_id=user_id).first()
    if existing and existing.file_path:
        if existing.file_path.startswith("/uploads/"):
            old_abs = abs_path_from_rel(existing.file_path)
            if os.path.exists(old_abs):
                os.remove(old_abs)
        db.session.delete(existing)

    # guardar nuevo
    filename = f"cv_{user_id}.pdf"
    abs_dest = os.path.join(cv_dir(), filename)
    file.save(abs_dest)

    rel = rel_url_for(filename)
    new_cv = CV(file_path=rel, user_id=user_id)
    db.session.add(new_cv)
    db.session.commit()

    return jsonify({"message": "CV subido exitosamente", "cv_url": rel}), 200


# Descargar CV (público)
@cv_bp.route('/download', methods=['GET'])
def public_download_cv():
    # Tomamos el primer CV disponible (si usas 1 usuario)
    cv = CV.query.first()
    if not cv or not cv.file_path:
        return jsonify({"error": "CV no disponible"}), 404

    # cv.file_path es "/uploads/cvs/xxx.pdf"
    rel = cv.file_path.replace("/uploads/", "")  # -> "cvs/xxx.pdf"
    return send_from_directory(uploads_root(), rel, as_attachment=True)


# Eliminar CV (cliente)
@cv_bp.route('/', methods=['DELETE'])
@jwt_required()
def delete_cv():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    cv = CV.query.filter_by(user_id=user_id).first()
    if not cv or not cv.file_path:
        return jsonify({"error": "No CV to delete"}), 404

    if cv.file_path.startswith("/uploads/"):
        abs_p = abs_path_from_rel(cv.file_path)
        if os.path.exists(abs_p):
            os.remove(abs_p)

    db.session.delete(cv)
    db.session.commit()
    return jsonify({"message": "CV eliminado correctamente"}), 200
