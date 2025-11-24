from flask import Blueprint, request, jsonify, send_from_directory, current_app
from models import Category, ProjectImage, ProjectVideo, db
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
import time, random, string

categories_bp = Blueprint('categories', __name__)

# === CONFIG / HELPERS =========================================================

ALLOWED_IMG = {'.png', '.jpg', '.jpeg', '.webp'}
ALLOWED_VID = {'.mp4', '.webm', '.ogg'}

def uploads_root():
    # Define en config.py: UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
    return current_app.config.get("UPLOADS_DIR", os.path.join(current_app.root_path, "uploads"))

def abs_path(*parts):
    return os.path.join(uploads_root(), *parts)

def rel_url(*parts):
    return "/uploads/" + "/".join(parts)

def ensure_dirs():
    os.makedirs(abs_path("projects", "images"), exist_ok=True)
    os.makedirs(abs_path("projects", "videos"), exist_ok=True)

def remove_local_if_needed(rel_url_path: str):
    # si empieza por /uploads/ lo borro del disco
    if rel_url_path and rel_url_path.startswith("/uploads/"):
        rel = rel_url_path.replace("/uploads/", "")
        full = abs_path(rel)
        if os.path.exists(full):
            try:
                os.remove(full)
            except Exception:
                pass

def gen_slide_key() -> str:
    rnd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"s{int(time.time())}{rnd}"

def parse_bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y", "on"}

# === SERVIR ARCHIVOS ==========================================================

@categories_bp.route('/uploads/<path:filename>', methods=['GET'])
def serve_uploaded_file(filename):
    # Sirve TODO desde la carpeta UPLOADS_DIR
    return send_from_directory(uploads_root(), filename)

# === CATEGORÍAS (PÚBLICO) =====================================================

@categories_bp.route('/public', methods=['GET'])
def get_public_categories():
    categories = Category.query.order_by(Category.order).all()
    return jsonify([
        {"id": c.id, "name": c.name, "order": c.order, "slug": getattr(c, "slug", str(c.id))}
        for c in categories
    ]), 200

@categories_bp.route('/<int:category_id>/detail', methods=['GET'])
def get_category_detail(category_id):
    category = Category.query.get_or_404(category_id)

    def _img_dict(img):
        return {
            "id": img.id,
            "image_url": img.image_url,
            "description": getattr(img, "description", None),
            "position": img.position,
            "is_carousel": getattr(img, "is_carousel", False),
            "slide_key": getattr(img, "slide_key", None),
            "type": "image",
            "url": img.image_url,
        }

    def _vid_dict(vid):
        return {
            "id": vid.id,
            "video_url": vid.video_url,
            "description": getattr(vid, "description", None),
            "position": vid.position,
            "is_carousel": getattr(vid, "is_carousel", False),
            "slide_key": getattr(vid, "slide_key", None),
            "type": "video",
            "url": vid.video_url,
        }

    images = [_img_dict(img) for img in category.images]
    videos = [_vid_dict(vid) for vid in category.videos]

    all_blocks = images + videos
    all_blocks.sort(key=lambda x: (x["position"] or 0, x["id"]))

    # Slides del carrusel
    slides = [b for b in all_blocks if b.get("is_carousel")]

    # Subcontenido agrupado por slide_key
    by_slide = {}
    for b in all_blocks:
        if not b.get("is_carousel") and b.get("slide_key"):
            by_slide.setdefault(b["slide_key"], []).append(b)

    for sk in by_slide:
        by_slide[sk].sort(key=lambda x: (x["position"] or 0, x["id"]))

    return jsonify({
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "images": images,        # compat
        "videos": videos,        # compat
        "timeline": all_blocks,  # compat: carrusel mixto básico
        "slides": slides,        # NUEVO: lista de slides con slide_key
        "by_slide": by_slide,    # NUEVO: sub-bloques de cada slide
    }), 200

# === CATEGORÍAS (ADMIN) =======================================================

@categories_bp.route('', methods=['GET'])
@jwt_required()
def get_categories():
    user_id = int(get_jwt_identity())
    categories = Category.query.filter_by(user_id=user_id).order_by(Category.order).all()
    return jsonify([{"id": c.id, "name": c.name, "order": c.order} for c in categories]), 200

@categories_bp.route('', methods=['POST'])
@jwt_required()
def create_category():
    """Crea categoría VACÍA (sin archivos). Luego añadirás media uno a uno."""
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    description = data.get('description') or ''
    if not name:
        return jsonify({"error": "El nombre de la categoría es obligatorio"}), 400

    max_order = db.session.query(db.func.max(Category.order)).scalar() or 0
    category = Category(name=name, description=description, user_id=user_id, order=max_order + 1)
    db.session.add(category)
    db.session.commit()
    return jsonify({"id": category.id, "name": category.name}), 201

# ---- REORDENAR TODAS LAS CATEGORÍAS (↑ / ↓) ---------------------------------

@categories_bp.route('/reorder', methods=['PUT'])
@jwt_required()
def reorder_categories():
    """
    Reordena TODAS las categorías del usuario.
    Body JSON: { "ordered_ids": [3, 5, 2, ...] }
    """
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    ordered_ids = data.get('ordered_ids')

    if not isinstance(ordered_ids, list) or not all(isinstance(x, int) for x in ordered_ids):
        return jsonify({"error": "ordered_ids debe ser un array de enteros"}), 400

    # categorías del usuario
    cats = Category.query.filter_by(user_id=user_id).all()
    ids_user = {c.id for c in cats}

    # validar pertenencia
    if not set(ordered_ids).issubset(ids_user):
        return jsonify({"error": "Hay ids que no pertenecen a este usuario"}), 400

    # por si faltan ids, añadirlos al final
    missing = [cid for cid in ids_user if cid not in ordered_ids]
    final_order = ordered_ids + missing

    # aplicar orden incremental
    for idx, cid in enumerate(final_order, start=1):
        cat = next(c for c in cats if c.id == cid)
        cat.order = idx

    db.session.commit()
    return jsonify({"message": "Orden actualizado"}), 200

# === MEDIA: AÑADIR / REEMPLAZAR / BORRAR UNO A UNO ============================

@categories_bp.route('/<int:category_id>/media', methods=['POST'])
@jwt_required()
def add_media(category_id):
    """Añade UNA imagen o UN video: archivo (form-data) o url (JSON).
       Requiere type=image|video. Soporta description, position, is_carousel y slide_key."""
    user_id = int(get_jwt_identity())
    ensure_dirs()

    category = Category.query.filter_by(id=category_id, user_id=user_id).first()
    if not category:
        return jsonify({"error": "Categoría no encontrada"}), 404

    media_type = None
    description = None
    pos_str = None
    is_carousel = False
    slide_key = None

    if request.content_type and request.content_type.startswith('multipart/form-data'):
        media_type = (request.form.get('type') or '').lower()
        description = request.form.get('description') or None
        pos_str = request.form.get('position')
        is_carousel = parse_bool(request.form.get('is_carousel'))
        slide_key = (request.form.get('slide_key') or '').strip() or None
    elif request.is_json:
        body = request.get_json() or {}
        media_type = (body.get('type') or '').lower()
        description = body.get('description') or None
        pos_str = body.get('position')
        is_carousel = parse_bool(body.get('is_carousel'))
        slide_key = (body.get('slide_key') or '').strip() or None

    if media_type not in ('image', 'video'):
        return jsonify({"error": "type debe ser 'image' o 'video'"}), 400

    # position global (mezcla imágenes y videos)
    max_img = db.session.query(db.func.max(ProjectImage.position)).filter_by(category_id=category.id).scalar() or 0
    max_vid = db.session.query(db.func.max(ProjectVideo.position)).filter_by(category_id=category.id).scalar() or 0
    next_pos = max(max_img, max_vid) + 1

    if pos_str is not None:
        try:
            next_pos = int(pos_str)
        except (TypeError, ValueError):
            return jsonify({"error": "position debe ser entero"}), 400

    # Si es slide y no hay slide_key, la generamos
    if is_carousel and not slide_key:
        slide_key = gen_slide_key()

    # --- A) archivo (form-data) ---
    if request.content_type and request.content_type.startswith('multipart/form-data') and 'file' in request.files:
        f = request.files['file']
        if not f or not f.filename:
            return jsonify({"error": "Archivo vacío"}), 400
        filename = secure_filename(f.filename)
        ext = os.path.splitext(filename)[1].lower()

        if media_type == 'image' and ext not in ALLOWED_IMG:
            return jsonify({"error": "Imagen no válida"}), 400
        if media_type == 'video' and ext not in ALLOWED_VID:
            return jsonify({"error": "Video no válido"}), 400

        dest_rel = ("projects", "images", filename) if media_type == 'image' else ("projects", "videos", filename)
        f.save(abs_path(*dest_rel))
        url_rel = rel_url(*dest_rel)

        if media_type == 'image':
            m = ProjectImage(image_url=url_rel, description=description, position=next_pos,
                             category_id=category.id, is_carousel=is_carousel, slide_key=slide_key)
        else:
            m = ProjectVideo(video_url=url_rel, description=description, position=next_pos,
                             category_id=category.id, is_carousel=is_carousel, slide_key=slide_key)

        db.session.add(m)
        db.session.commit()
        return jsonify({
            "message": "Añadido",
            "id": m.id,
            "url": url_rel,
            "description": description,
            "position": next_pos,
            "is_carousel": is_carousel,
            "slide_key": slide_key
        }), 201

    # --- B) url (JSON) ---
    if request.is_json:
        data = request.get_json() or {}
        url = (data.get('url') or '').strip()
        if not url:
            return jsonify({"error": "url requerida"}), 400

        if media_type == 'image':
            m = ProjectImage(image_url=url, description=description, position=next_pos,
                             category_id=category.id, is_carousel=is_carousel, slide_key=slide_key)
        else:
            m = ProjectVideo(video_url=url, description=description, position=next_pos,
                             category_id=category.id, is_carousel=is_carousel, slide_key=slide_key)

        db.session.add(m)
        db.session.commit()
        return jsonify({
            "message": "Añadido",
            "id": m.id,
            "url": url,
            "description": description,
            "position": next_pos,
            "is_carousel": is_carousel,
            "slide_key": slide_key
        }), 201

    return jsonify({"error": "Usa form-data (file) o JSON (url)"}), 415


@categories_bp.route('/media/<int:media_id>', methods=['PUT'])
@jwt_required()
def replace_media(media_id):
    """Reemplaza UNA media por archivo (form-data) o por nueva URL (JSON).
       También permite actualizar description, position, is_carousel y slide_key."""
    ensure_dirs()

    img = ProjectImage.query.get(media_id)
    vid = None if img else ProjectVideo.query.get(media_id)
    if not img and not vid:
        return jsonify({"error": "Media no encontrada"}), 404

    target = img or vid
    changed = False

    # A) archivo (form-data)
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        # reemplazo de archivo
        if 'file' in request.files:
            f = request.files['file']
            if not f or not f.filename:
                return jsonify({"error": "Archivo vacío"}), 400
            filename = secure_filename(f.filename)
            ext = os.path.splitext(filename)[1].lower()

            if img and ext not in ALLOWED_IMG:
                return jsonify({"error": "Imagen no válida"}), 400
            if vid and ext not in ALLOWED_VID:
                return jsonify({"error": "Video no válido"}), 400

            if img:
                dest_rel = ("projects", "images", filename)
                remove_local_if_needed(img.image_url)
                f.save(abs_path(*dest_rel))
                img.image_url = rel_url(*dest_rel)
            else:
                dest_rel = ("projects", "videos", filename)
                remove_local_if_needed(vid.video_url)
                f.save(abs_path(*dest_rel))
                vid.video_url = rel_url(*dest_rel)

            changed = True

        # metadatos
        description = request.form.get('description')
        position = request.form.get('position')
        is_carousel_val = request.form.get('is_carousel')
        slide_key_val = request.form.get('slide_key')

        if description is not None:
            target.description = description or None
            changed = True
        if position is not None:
            try:
                target.position = int(position)
                changed = True
            except ValueError:
                return jsonify({"error": "position debe ser entero"}), 400
        if is_carousel_val is not None:
            target.is_carousel = parse_bool(is_carousel_val)
            changed = True
        if slide_key_val is not None:
            sk = (slide_key_val or '').strip()
            target.slide_key = sk if sk else None
            changed = True

        if changed:
            db.session.commit()
            return jsonify({
                "message": "Actualizado",
                "url": getattr(target, 'image_url', None) or getattr(target, 'video_url', None),
                "description": target.description,
                "position": target.position,
                "is_carousel": target.is_carousel,
                "slide_key": target.slide_key
            }), 200

        return jsonify({"message": "Sin cambios"}), 200

    # B) JSON
    if request.is_json:
        data = request.get_json() or {}
        url = (data.get('url') or '').strip()
        description = data.get('description')
        position = data.get('position')
        is_carousel_val = data.get('is_carousel')
        slide_key_val = data.get('slide_key')

        if url:
            old_url = getattr(target, 'image_url', None) or getattr(target, 'video_url', None)
            remove_local_if_needed(old_url)
            if img:
                img.image_url = url
            else:
                vid.video_url = url
            changed = True

        if description is not None:
            target.description = description or None
            changed = True

        if position is not None:
            try:
                target.position = int(position)
                changed = True
            except ValueError:
                return jsonify({"error": "position debe ser entero"}), 400

        if is_carousel_val is not None:
            target.is_carousel = parse_bool(is_carousel_val)
            changed = True

        if slide_key_val is not None:
            sk = (slide_key_val or '').strip()
            target.slide_key = sk if sk else None
            changed = True

        if changed:
            db.session.commit()
            return jsonify({
                "message": "Actualizado",
                "url": getattr(target, 'image_url', None) or getattr(target, 'video_url', None),
                "description": target.description,
                "position": target.position,
                "is_carousel": target.is_carousel,
                "slide_key": target.slide_key
            }), 200

        return jsonify({"error": "Proporciona archivo/url/description/position/is_carousel/slide_key"}), 400

    return jsonify({"error": "Proporciona form-data o JSON"}), 415


@categories_bp.route('/media/<int:media_id>/meta', methods=['PATCH'])
@jwt_required()
def update_media_meta(media_id):
    """Actualiza SOLO metadatos: description, position, is_carousel y/o slide_key."""
    target = ProjectImage.query.get(media_id) or ProjectVideo.query.get(media_id)
    if not target:
        return jsonify({"error": "Media no encontrada"}), 404

    data = request.get_json() or {}
    changed = False

    if 'description' in data:
        desc = data.get('description')
        target.description = desc if desc else None
        changed = True

    if 'position' in data:
        try:
            target.position = int(data.get('position'))
            changed = True
        except (TypeError, ValueError):
            return jsonify({"error": "position debe ser un número"}), 400

    if 'is_carousel' in data:
        target.is_carousel = parse_bool(data.get('is_carousel'))
        changed = True

    if 'slide_key' in data:
        sk = (data.get('slide_key') or '').strip()
        target.slide_key = sk if sk else None
        changed = True

    if changed:
        db.session.commit()
        return jsonify({
            "message": "Metadatos actualizados",
            "description": target.description,
            "position": target.position,
            "is_carousel": target.is_carousel,
            "slide_key": target.slide_key
        }), 200

    return jsonify({"message": "Sin cambios"}), 200


@categories_bp.route('/media/<int:media_id>', methods=['DELETE'])
@jwt_required()
def delete_media(media_id):
    """Elimina UNA media (y el archivo local si aplica)."""
    m = ProjectImage.query.get(media_id) or ProjectVideo.query.get(media_id)
    if not m:
        return jsonify({"error": "Media no encontrada"}), 404

    url = m.image_url if hasattr(m, 'image_url') else m.video_url
    remove_local_if_needed(url)
    db.session.delete(m)
    db.session.commit()
    return jsonify({"message": "Eliminado"}), 200

# === BORRAR CATEGORÍA COMPLETA ================================================

@categories_bp.route('/<int:category_id>', methods=['DELETE'])
@jwt_required()
def delete_category(category_id):
    user_id = int(get_jwt_identity())
    category = Category.query.filter_by(id=category_id, user_id=user_id).first()
    if not category:
        return jsonify({"error": "Categoría no encontrada"}), 404

    for image in category.images:
        remove_local_if_needed(image.image_url)
        db.session.delete(image)

    for video in category.videos:
        remove_local_if_needed(video.video_url)
        db.session.delete(video)

    db.session.delete(category)
    db.session.commit()
    return jsonify({"message": "Categoría y contenido eliminados"}), 200
