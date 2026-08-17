import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Tuple
from dotenv import load_dotenv
from app.core.config import settings, root_env_path
from app.utils.logger import logger

class EmailService:
    """
    Robust service responsible for sending transactional emails via SMTP.
    Validates configuration strictly and ensures real delivery confirmation.
    """

    def send_user_credentials_email(
        self,
        to_email: str,
        user_name: str,
        initial_password: str
    ) -> Tuple[bool, str]:
        """
        Sends the login credentials email to a newly created user.
        Returns (success: bool, message: str).
        """
        # Reload latest .env from disk so runtime edits take effect immediately
        if os.path.exists(root_env_path):
            load_dotenv(dotenv_path=root_env_path, override=True)

        host = settings.get_smtp_host()
        port = settings.get_smtp_port()
        user = settings.get_smtp_user()
        password = settings.get_smtp_password()
        use_tls = settings.get_smtp_use_tls()
        from_email = settings.get_smtp_from_email()
        from_name = settings.get_smtp_from_name()

        logger.info(f"[EMAIL SERVICE] Step 1: Received credentials email request for recipient='{to_email}'.")

        # 1. Strict Configuration Validation
        if not user or not password:
            error_msg = (
                "SMTP configuration is missing or incomplete. "
                "Please configure SMTP_USER (or SMTP_USERNAME) and SMTP_PASSWORD in the root .env file."
            )
            logger.error(f"[EMAIL SERVICE] Delivery aborted: {error_msg}")
            return False, error_msg

        if not host:
            error_msg = "SMTP_HOST is not configured in the root .env file."
            logger.error(f"[EMAIL SERVICE] Delivery aborted: {error_msg}")
            return False, error_msg

        # 2. Build Email Payload
        subject = "Welcome to Talent Management Platform for Employee Performance and Career Growth – Your Login Credentials"

        # Plain text version matching user specification exactly
        plain_body = f"""Hello,

You have been added as a user to Talent Management Platform for Employee Performance and Career Growth.

You can now access your dashboard using the credentials provided below.

Login Credentials

Email: {to_email}
Password: {initial_password}

Please use these credentials to log in to your Talent Management Platform for Employee Performance and Career Growth dashboard.

Regards,
Talent Management Platform for Employee Performance and Career Growth Team
"""

        # Modern HTML formatted version
        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b0f19; color: #f1f5f9; margin: 0; padding: 20px; }}
    .card {{ max-width: 540px; margin: 0 auto; background-color: #111827; border: 1px solid #374151; border-radius: 16px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
    .header {{ border-bottom: 1px solid #1f2937; padding-bottom: 20px; margin-bottom: 24px; }}
    .header h2 {{ margin: 0; color: #6366f1; font-size: 18px; }}
    .content {{ font-size: 14px; line-height: 1.6; color: #cbd5e1; }}
    .credentials-box {{ background-color: #1e1b4b; border: 1px solid #4f46e5; border-radius: 12px; padding: 18px; margin: 24px 0; }}
    .credential-row {{ margin: 8px 0; font-size: 14px; }}
    .credential-label {{ font-weight: bold; color: #818cf8; width: 80px; display: inline-block; }}
    .credential-val {{ font-family: monospace; font-weight: bold; color: #ffffff; background-color: #312e81; padding: 2px 8px; border-radius: 6px; }}
    .footer {{ margin-top: 32px; padding-top: 20px; border-top: 1px solid #1f2937; font-size: 13px; color: #94a3b8; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h2>Talent Management Platform for Employee Performance and Career Growth</h2>
    </div>
    <div class="content">
      <p>Hello,</p>
      <p>You have been added as a user to <strong>Talent Management Platform for Employee Performance and Career Growth</strong>.</p>
      <p>You can now access your dashboard using the credentials provided below.</p>
      
      <div class="credentials-box">
        <h4 style="margin: 0 0 12px 0; color: #c7d2fe; font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em;">Login Credentials</h4>
        <div class="credential-row">
          <span class="credential-label">Email:</span>
          <span class="credential-val">{to_email}</span>
        </div>
        <div class="credential-row">
          <span class="credential-label">Password:</span>
          <span class="credential-val">{initial_password}</span>
        </div>
      </div>

      <p>Please use these credentials to log in to your dashboard.</p>
    </div>
    <div class="footer">
      <p style="margin: 0;"><strong>Regards,</strong><br>Talent Management Platform for Employee Performance and Career Growth Team</p>
    </div>
  </div>
</body>
</html>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email

        msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        server = None
        try:
            # 3. SMTP Connection
            logger.info(f"[EMAIL SERVICE] Step 2: Connecting to SMTP server at '{host}:{port}' (SSL={port == 465}, TLS={use_tls})...")
            
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=15)
                server.ehlo()
            else:
                server = smtplib.SMTP(host, port, timeout=15)
                server.ehlo()
                if use_tls:
                    logger.info(f"[EMAIL SERVICE] Initiating STARTTLS negotiation with '{host}'...")
                    server.starttls()
                    server.ehlo()

            # 4. SMTP Authentication (Never logging password)
            logger.info(f"[EMAIL SERVICE] Step 3: Authenticating with SMTP server as user='{user}'...")
            server.login(user, password)
            logger.info(f"[EMAIL SERVICE] Step 4: SMTP authentication successful.")

            # 5. Message Dispatch
            logger.info(f"[EMAIL SERVICE] Step 5: Sending credentials email from='{from_email}' to='{to_email}'...")
            server.sendmail(from_email, [to_email], msg.as_string())
            
            logger.info(f"[EMAIL SERVICE] Step 6: Email accepted and delivered by SMTP server for recipient='{to_email}'.")
            return True, f"Login credentials sent successfully to {to_email}."

        except smtplib.SMTPAuthenticationError as e:
            error_details = (
                f"SMTP Authentication failed for '{user}'. "
                "If using Gmail, please ensure you use a 16-character Gmail App Password (with 2-Step Verification enabled) "
                "instead of your personal Google account password."
            )
            logger.error(f"[EMAIL SERVICE] Authentication Error: {error_details} (Code: {getattr(e, 'smtp_code', 'N/A')})")
            return False, error_details

        except (smtplib.SMTPConnectError, ConnectionRefusedError, TimeoutError, OSError) as e:
            error_details = f"Could not connect to SMTP server at '{host}:{port}': {str(e)}"
            logger.error(f"[EMAIL SERVICE] Connection Error: {error_details}")
            return False, error_details

        except smtplib.SMTPRecipientsRefused as e:
            error_details = f"The recipient email address '{to_email}' was refused by the mail server: {str(e)}"
            logger.error(f"[EMAIL SERVICE] Recipient Refused: {error_details}")
            return False, error_details

        except smtplib.SMTPSenderRefused as e:
            error_details = f"The sender email address '{from_email}' was refused by the mail server: {str(e)}"
            logger.error(f"[EMAIL SERVICE] Sender Refused: {error_details}")
            return False, error_details

        except smtplib.SMTPException as e:
            error_details = f"SMTP transmission error: {str(e)}"
            logger.error(f"[EMAIL SERVICE] SMTP Error: {error_details}")
            return False, error_details

        except Exception as e:
            error_details = f"Failed to send email: {str(e)}"
            logger.error(f"[EMAIL SERVICE] Unexpected Error: {error_details}", exc_info=True)
            return False, error_details

        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

email_service = EmailService()
