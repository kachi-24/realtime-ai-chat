import asyncio

from email_service import send_verification_email


async def main():

    await send_verification_email(
        "agbo1526@gmail.com",
        "test-verification-token",
    )

    print("Verification email sent successfully!")


if __name__ == "__main__":
    asyncio.run(main())