from datetime import datetime, timezone
import re
from extensions import db

def slugify(text: str) -> str:
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', text or '')
    text = re.sub(r'\s+', '-', text).strip('-').lower()
    return text or 'categoria'


# ---------------- Usuario ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))


# ---------------- Categoría ----------------
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(120), nullable=True, index=True)
    description = db.Column(db.Text, nullable=True)
    order = db.Column(db.Integer, nullable=False, default=0, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('categories', lazy=True))

    images = db.relationship(
        'ProjectImage',
        backref='category',
        lazy=True,
        cascade="all, delete-orphan",
        order_by="ProjectImage.position"
    )
    videos = db.relationship(
        'ProjectVideo',
        backref='category',
        lazy=True,
        cascade="all, delete-orphan",
        order_by="ProjectVideo.position"
    )

    def ensure_slug(self):
        if not self.slug and self.name:
            self.slug = slugify(self.name)


# ---------------- Media: Imágenes ----------------
class ProjectImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(512), nullable=False)
    description = db.Column(db.Text, nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0, index=True)

    is_carousel = db.Column(db.Boolean, nullable=False, default=False, index=True)
    slide_key = db.Column(db.String(64), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    category_id = db.Column(db.Integer, db.ForeignKey('category.id', ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        db.Index('ix_img_cat_slide', 'category_id', 'slide_key'),
    )


# ---------------- Media: Videos ----------------
class ProjectVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_url = db.Column(db.String(512), nullable=False)
    description = db.Column(db.Text, nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0, index=True)

    is_carousel = db.Column(db.Boolean, nullable=False, default=False, index=True)
    slide_key = db.Column(db.String(64), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    category_id = db.Column(db.Integer, db.ForeignKey('category.id', ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        db.Index('ix_vid_cat_slide', 'category_id', 'slide_key'),
    )


# ---------------- Mensajes ----------------
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('messages', lazy=True))


# ---------------- CV (uno por usuario) ----------------
class CV(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String(512), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    user = db.relationship('User', backref=db.backref('cv', lazy=True, uselist=False))


# ---------------- Redes sociales ----------------
class SocialLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(30), nullable=False)   # 'linkedin' | 'artstation'
    url = db.Column(db.String(512), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    __table_args__ = (
        db.UniqueConstraint('user_id', 'platform', name='uq_user_platform'),
    )


# ---------------- Contact Page (contenido editable) ----------------
class ContactPage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, default="Contacto")
    intro = db.Column(db.Text, nullable=True)
    body = db.Column(db.Text, nullable=True)
    videos_json = db.Column(db.Text, nullable=True)
    hero_image_url = db.Column(db.String(512), nullable=True)

    # ✅ NUEVO CAMPO — se guarda el párrafo que tu cliente edita
    footer_note = db.Column(db.Text, nullable=True, default="")

    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc),
                           onupdate=datetime.now(timezone.utc))

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


# ---------------- Hooks ----------------
from sqlalchemy import event

@event.listens_for(Category, "before_insert")
def set_slug_before_insert(mapper, connection, target: Category):
    target.ensure_slug()

@event.listens_for(Category, "before_update")
def set_slug_before_update(mapper, connection, target: Category):
    if not target.slug:
        target.ensure_slug()
