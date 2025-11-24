# routes/socials.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, SocialLink

socials_bp = Blueprint("socials", __name__)
ALLOWED = {"linkedin", "artstation"}

def normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u

@socials_bp.get("/public")
def socials_public():
    rows = SocialLink.query.filter(SocialLink.platform.in_(ALLOWED)).all()
    data = {s.platform: {"platform": s.platform, "url": s.url} for s in rows}
    return jsonify({
        "linkedin": data.get("linkedin"),
        "artstation": data.get("artstation"),
    }), 200

@socials_bp.route("", methods=["POST"])
@socials_bp.route("/", methods=["POST"])
@jwt_required()
def upsert_social():
    user_id = int(get_jwt_identity())
    body = request.get_json() or {}
    platform = (body.get("platform") or "").lower().strip()
    url = normalize_url(body.get("url", ""))

    if platform not in ALLOWED:
        return jsonify({"error": "platform debe ser 'linkedin' o 'artstation'"}), 400
    if not url:
        return jsonify({"error": "url requerida"}), 400

    row = SocialLink.query.filter_by(user_id=user_id, platform=platform).first()
    if row:
        row.url = url
    else:
        db.session.add(SocialLink(platform=platform, url=url, user_id=user_id))

    db.session.commit()
    return jsonify({"message": "guardado", "platform": platform, "url": url}), 200

@socials_bp.delete("/<platform>")
@jwt_required()
def delete_social(platform):
    user_id = int(get_jwt_identity())
    p = (platform or "").lower()
    if p not in ALLOWED:
        return jsonify({"error": "platform inválida"}), 400

    row = SocialLink.query.filter_by(user_id=user_id, platform=p).first()
    if row:
        db.session.delete(row)
        db.session.commit()
    return "", 204
