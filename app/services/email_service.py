import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body_html: str, body_text: str | None = None) -> bool:
    """Send an email using SMTP (configured for SendGrid SMTP)."""
    settings = get_settings()

    mail_host = settings.mail_host
    mail_port = settings.mail_port
    mail_user = settings.mail_username
    mail_pass = settings.mail_password.get_secret_value()
    from_addr = settings.mail_from_address
    from_name = settings.mail_from_name

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
    msg["To"] = to_email

    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    if not mail_pass:
        logger.warning(
            f"[MOCK EMAIL] MAIL_PASSWORD not configured. Skipping SMTP send to {to_email}. "
            f"Subject: {subject}"
        )
        return True

    try:
        with smtplib.SMTP(mail_host, mail_port, timeout=15) as server:
            if settings.mail_encryption.lower() == "tls":
                server.starttls()
            if mail_user and mail_pass:
                server.login(mail_user, mail_pass)
            server.sendmail(from_addr, [to_email], msg.as_string())
        logger.info(f"Successfully sent email to {to_email} via SMTP ({mail_host}:{mail_port})")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email} via SMTP ({mail_host}:{mail_port}): {e}")
        return False


def send_password_reset_email(to_email: str, username: str, reset_link: str) -> bool:
    """Send a password reset email to a user."""
    settings = get_settings()
    app_name = "UshuruLens"
    subject = f"Password Reset Request — {app_name}"

    body_text = (
        f"Hello {username},\n\n"
        f"You requested a password reset for your {app_name} account.\n"
        f"Please click or copy the following link into your browser to reset your password:\n\n"
        f"{reset_link}\n\n"
        f"This link will expire in {settings.password_reset_token_expire_minutes} minutes.\n"
        f"If you did not request a password reset, please ignore this email.\n\n"
        f"Regards,\n{settings.mail_from_name}"
    )

    body_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Password Reset Request</title>
</head>
<body style="margin:0; padding:0; background-color:#f8fafc; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color:#f8fafc; padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width:540px; background-color:#ffffff; border-radius:16px; border:1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); overflow:hidden;">
          
          <!-- Header Banner -->
          <tr>
            <td style="background-color:#0e1734; padding:28px 32px; text-align:center;">
              <h1 style="color:#ffffff; margin:0; font-size:20px; font-weight:700; tracking-tight">{app_name}</h1>
              <p style="color:#94a3b8; margin:4px 0 0 0; font-size:12px; font-weight:500;">Secure Identity & Account Services</p>
            </td>
          </tr>

          <!-- Content Body -->
          <tr>
            <td style="padding:32px; color:#334155; font-size:14px; line-height:1.6;">
              <p style="margin:0 0 16px 0; font-size:15px; font-weight:600; color:#0f172a;">
                Hello @{username},
              </p>
              <p style="margin:0 0 20px 0;">
                We received a request to reset your password for your account on <strong>{app_name}</strong>.
              </p>
              
              <div style="text-align:center; margin:28px 0;">
                <a href="{reset_link}" target="_blank" style="background-color:#0e1734; color:#ffffff; font-weight:600; text-decoration:none; padding:12px 28px; border-radius:10px; font-size:14px; display:inline-block; box-shadow: 0 2px 4px rgba(14, 23, 52, 0.2);">
                  Reset Your Password &rarr;
                </a>
              </div>

              <p style="margin:0 0 16px 0; font-size:12px; color:#64748b;">
                Or copy and paste this link into your browser address bar:
              </p>
              <div style="background-color:#f1f5f9; border:1px solid #e2e8f0; border-radius:8px; padding:10px 14px; font-size:12px; font-family: monospace; word-break:break-all; color:#0f172a; margin-bottom:24px;">
                {reset_link}
              </div>

              <div style="border-top:1px solid #f1f5f9; padding-top:16px; margin-top:24px; font-size:12px; color:#94a3b8;">
                <p style="margin:0 0 4px 0;"><strong>Security Notice:</strong> This link will expire in <strong>{settings.password_reset_token_expire_minutes} minutes</strong>.</p>
                <p style="margin:0;">If you did not request this password reset, no action is required and your password will remain unchanged.</p>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#f8fafc; border-top:1px solid #e2e8f0; padding:16px 32px; text-align:center; font-size:11px; color:#94a3b8;">
              &copy; {app_name}. Powered by {settings.mail_from_name}.
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    return send_email(to_email, subject, body_html, body_text)
