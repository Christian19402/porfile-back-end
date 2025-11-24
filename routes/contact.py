# routes/contact.py
import json
import os
import time, random, string
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from models import db, ContactPage
from routes.categories import abs_path, rel_url, ensure_dirs  # reutilizamos helpers de uploads

contact_bp = Blueprint("contact", __name__)

ALLOWED_IMG = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_VID = {".mp4", ".webm", ".ogg"}


# ======================================================
# Helpers internos
# ======================================================

def _get_or_create_contact(user_id: int) -> ContactPage:
    cp = ContactPage.query.filter_by(user_id=user_id).first()
    if not cp:
        cp = ContactPage(
            user_id=user_id,
            title="Contacto",
            intro="",
            body="",
            footer_note="",
            videos_json="[]",
            hero_image_url=None,  # solo para compatibilidad si el modelo lo tiene
        )
        db.session.add(cp)
        db.session.commit()
    return cp


def _parse_blocks(s: str):
    try:
        data = json.loads(s or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _safe_blocks(blocks):
    """
    Bloques válidos:
      { "type":"text",  "content":"...",                          "position": 1 }
      { "type":"image", "url":"/uploads/...", "caption":"",       "position": 2, "in_carousel": true|false }
      { "type":"video", "url":"https://…|/uploads/video.mp4",     "position": 3, "in_carousel": true|false }
    """
    out = []
    for b in blocks or []:
        t = (b.get("type") or "").lower()
        if t not in ("text", "image", "video"):
            continue

        item = {"type": t, "position": int(b.get("position") or 0)}

        if t == "text":
            item["content"] = b.get("content") or ""
        else:
            item["url"] = b.get("url") or ""
            item["caption"] = b.get("caption") or ""
            # NUEVO: flag para carrusel (por defecto False)
            item["in_carousel"] = bool(b.get("in_carousel", False))

        out.append(item)

    out.sort(key=lambda x: (x.get("position", 0)))
    return out


def _unique_name(filename: str) -> str:
    base, ext = os.path.splitext(filename)
    rnd = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{int(time.time())}_{rnd}{ext.lower()}"


# ======================================================
# Público
# ======================================================

@contact_bp.route("/public", methods=["GET"])
def contact_public():
    cp = ContactPage.query.order_by(ContactPage.id.asc()).first()
    if not cp:
        return jsonify({
            "title": "Contacto",
            "intro": "",
            "body": "",
            "footer_note": "",
            "hero_image_url": None,
            "blocks": []
        }), 200

    return jsonify({
        "title": cp.title,
        "intro": cp.intro,
        "body": cp.body,
        "footer_note": getattr(cp, "footer_note", "") or "",
        "hero_image_url": cp.hero_image_url,  # no se usa en frontend actual
        "blocks": _parse_blocks(cp.videos_json),
        "updated_at": cp.updated_at.isoformat() if getattr(cp, "updated_at", None) else None
    }), 200


# ======================================================
# Admin (JWT)
# ======================================================

@contact_bp.route("", methods=["GET"])
@jwt_required()
def contact_get():
    user_id = int(get_jwt_identity())
    cp = _get_or_create_contact(user_id)
    return jsonify({
        "title": cp.title,
        "intro": cp.intro,
        "body": cp.body,
        "footer_note": getattr(cp, "footer_note", "") or "",
        "hero_image_url": cp.hero_image_url,
        "blocks": _parse_blocks(cp.videos_json)
    }), 200


@contact_bp.route("", methods=["POST"])
@jwt_required()
def contact_save_texts():
    """Guarda los textos: title, intro, body y footer_note."""
    user_id = int(get_jwt_identity())
    cp = _get_or_create_contact(user_id)
    data = request.get_json() or {}

    if "title" in data:
        cp.title = data.get("title") or "Contacto"
    if "intro" in data:
        cp.intro = data.get("intro") or ""
    if "body" in data:
        cp.body = data.get("body") or ""
    if "footer_note" in data:
        cp.footer_note = data.get("footer_note") or ""

    db.session.commit()
    return jsonify({"message": "Contenido guardado"}), 200


@contact_bp.route("/blocks", methods=["PUT"])
@jwt_required()
def contact_save_blocks():
    """Reemplaza toda la lista de bloques (texto/imagen/video)."""
    user_id = int(get_jwt_identity())
    cp = _get_or_create_contact(user_id)
    data = request.get_json() or {}
    blocks = _safe_blocks(data.get("blocks") or [])
    cp.videos_json = json.dumps(blocks, ensure_ascii=False)
    db.session.commit()
    return jsonify({"message": "Bloques guardados", "blocks": blocks}), 200


# ======================================================
# Subidas locales (imagenes / videos)
# ======================================================

@contact_bp.route("/upload-image", methods=["POST"])
@jwt_required()
def upload_image():
    ensure_dirs()
    if "file" not in request.files:
        return jsonify({"error": "Falta archivo"}), 400

    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "Archivo vacío"}), 400

    filename = secure_filename(_unique_name(f.filename))
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMG:
        return jsonify({"error": "Extensión de imagen no permitida"}), 400

    dest_rel = ("contact", "images", filename)
    os.makedirs(abs_path(*dest_rel[:-1]), exist_ok=True)
    f.save(abs_path(*dest_rel))
    url_rel = rel_url(*dest_rel)
    return jsonify({"url": url_rel}), 201


@contact_bp.route("/upload-video", methods=["POST"])
@jwt_required()
def upload_video():
    ensure_dirs()
    if "file" not in request.files:
        return jsonify({"error": "Falta archivo"}), 400

    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "Archivo vacío"}), 400

    filename = secure_filename(_unique_name(f.filename))
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_VID:
        return jsonify({"error": "Extensión de video no permitida"}), 400

    dest_rel = ("contact", "videos", filename)
    os.makedirs(abs_path(*dest_rel[:-1]), exist_ok=True)
    f.save(abs_path(*dest_rel))
    url_rel = rel_url(*dest_rel)
    return jsonify({"url": url_rel}), 201
