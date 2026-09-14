import os

import resend
from dotenv import load_dotenv


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()


RESEND_API_KEY = os.getenv("RESEND_API_KEY")

EMAIL_FROM = os.getenv(
    "EMAIL_FROM",
    "onboarding@resend.dev",
)

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5174",
)


if not RESEND_API_KEY:
    raise RuntimeError(
        "RESEND_API_KEY is not configured"
    )


resend.api_key = RESEND_API_KEY


# =========================================================
# EMAIL VERIFICATION
# =========================================================

async def send_verification_email(
    recipient_email: str,
    verification_token: str,
) -> None:

    verification_url = (
        f"{FRONTEND_URL}/verify-email"
        f"?token={verification_token}"
    )

    params: resend.Emails.SendParams = {
        "from": EMAIL_FROM,
        "to": [recipient_email],
        "subject": "Verify your Real-Time AI Chat account",
        "html": f"""
        <!DOCTYPE html>
        <html>
        <body>

            <h2>Verify your email</h2>

            <p>
                Welcome to Real-Time AI Chat.
            </p>

            <p>
                Click the button below to verify your email
                address.
            </p>

            <p>
                <a
                    href="{verification_url}"
                    style="
                        display:inline-block;
                        padding:12px 20px;
                        background:#000;
                        color:#fff;
                        text-decoration:none;
                        border-radius:6px;
                    "
                >
                    Verify Email
                </a>
            </p>

            <p>
                This verification link expires in 24 hours.
            </p>

            <p>
                If you did not create this account,
                you can safely ignore this email.
            </p>

        </body>
        </html>
        """,
    }

    await resend.Emails.send_async(params)