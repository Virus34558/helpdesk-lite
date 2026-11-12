import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("helpdesk.email")


def smtp_configurado() -> bool:
    return bool(os.getenv("SMTP_HOST"))


def enviar_correo(destinatario: str, asunto: str, cuerpo: str) -> bool:
    """Envía un correo por SMTP. Sin SMTP_HOST solo registra el envío simulado."""
    if not smtp_configurado():
        logger.debug("Correo simulado para %s: %s", destinatario, asunto)
        return False

    remitente = os.getenv("SMTP_FROM") or os.getenv(
        "SMTP_USER", "no-reply@helpdesk.local"
    )
    mensaje = EmailMessage()
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)

    host = os.getenv("SMTP_HOST")
    puerto = int(os.getenv("SMTP_PORT", "587"))
    usuario = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    usar_tls = os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes", "on")

    with smtplib.SMTP(host, puerto, timeout=15) as smtp:
        if usar_tls:
            smtp.starttls()
        if usuario and password:
            smtp.login(usuario, password)
        smtp.send_message(mensaje)

    logger.info("Correo enviado a %s: %s", destinatario, asunto)
    return True


def enviar_correo_seguro(destinatario: str, asunto: str, cuerpo: str) -> bool:
    """Igual que enviar_correo, pero nunca propaga errores SMTP."""
    if not destinatario:
        return False
    try:
        return enviar_correo(destinatario, asunto, cuerpo)
    except Exception:
        logger.exception("No se pudo enviar el correo a %s", destinatario)
        return False
