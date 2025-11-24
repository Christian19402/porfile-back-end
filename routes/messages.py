# backend/messages.py
from flask import Blueprint, request, jsonify, current_app
import html, re, smtplib, ssl
from email.message import EmailMessage

messages_bp = Blueprint('messages', __name__)

# --- Validación simple ---
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def sanitize_text(s: str, maxlen: int = 5000) -> str:
    s = (s or "").strip()
    s = s[:maxlen]
    return html.escape(s)

# --- Envío de email por SMTP (Gmail con contraseña de aplicación u otro SMTP) ---
def send_mail(subject: str, body: str, to_email: str) -> None:
    host = current_app.config.get("MAIL_SERVER")
    port = int(current_app.config.get("MAIL_PORT", 587))
    use_tls = bool(current_app.config.get("MAIL_USE_TLS", True))
    use_ssl = bool(current_app.config.get("MAIL_USE_SSL", False))
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")
    timeout = float(current_app.config.get("MAIL_TIMEOUT", 15))

    if not (host and port and username and password and to_email):
        current_app.logger.warning("Email no enviado: configuración incompleta.")
        raise RuntimeError("Configuración de correo incompleta")
        
    if use_ssl and use_tls:
        current_app.logger.warning("Ambas opciones TLS y SSL activadas; usando SSL y deshabilitando TLS")
        use_tls = False


    msg = EmailMessage()
    msg["From"] = username
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()

    smtp_kwargs = {"host": host, "port": port, "timeout": timeout}

    if use_ssl:
        smtp_class = smtplib.SMTP_SSL
        smtp_kwargs["context"] = context
    else:
        smtp_class = smtplib.SMTP

    with smtp_class(**smtp_kwargs) as server:
        server.ehlo()
        if use_tls:
            server.starttls(context=context)
            server.ehlo()
        server.login(username, password)
        server.send_message(msg)

# ============================
# PÚBLICO: Enviar mensaje
# ============================
@messages_bp.route('', methods=['POST', 'OPTIONS'])
@messages_bp.route('/', methods=['POST', 'OPTIONS'])
def send_message():
    if request.method == 'OPTIONS':
        return ('', 204)

    data = request.get_json(silent=True) or {}

    name = sanitize_text(data.get('name', ''), maxlen=120)
    last_name = sanitize_text(data.get('last_name', ''), maxlen=120)
    email = (data.get('email') or '').strip()
    content = sanitize_text(data.get('content', ''), maxlen=5000)

    # Validaciones mínimas
    if not name or not last_name or not email or not content:
        return jsonify({"error": "Todos los campos son obligatorios"}), 400
    if len(content) < 5:
        return jsonify({"error": "El mensaje es demasiado corto"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Email no válido"}), 400

    # Preparar correo
    dest = current_app.config.get("CONTACT_DEST_EMAIL")
    if not dest:
        current_app.logger.error("CONTACT_DEST_EMAIL no configurado")
        return jsonify({"error": "Destino de contacto no configurado"}), 500

    subject = f"Nuevo mensaje del portfolio: {name} {last_name}"
    body = (
        f"Nombre: {name} {last_name}\n"
        f"Email: {email}\n\n"
        f"Mensaje:\n{content}\n\n"
        f"— Enviado desde el formulario del portfolio."
    )

    try:
        send_mail(subject, body, dest)
        return jsonify({"message": "Mensaje recibido", "email_sent": True}), 201
    except Exception:
        current_app.logger.exception("Fallo enviando email")
        # A tu elección: puedes responder 500 o 202 aceptado sin email.
        return jsonify({"error": "No se pudo enviar el email", "email_sent": False}), 500
