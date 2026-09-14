import * as Sentry from "@sentry/react";
import { useEffect, useState } from "react";
import { API_URL } from "./api";

export default function VerifyEmail() {
  const [status, setStatus] = useState(
    "Verifying your email..."
  );

  useEffect(() => {
    async function verify() {
      const params =
        new URLSearchParams(
          window.location.search
        );

      const token =
        params.get("token");

      if (!token) {
        setStatus(
          "Verification token is missing."
        );

        return;
      }

      try {
        const response =
          await fetch(
            `${API_URL}/auth/verify-email?token=${encodeURIComponent(token)}`,
            {
              credentials: "include",
            }
          );

        const data =
          await response.json();

        if (!response.ok) {
          // Invalid or expired verification tokens
          // are expected application responses,
          // so don't report them as exceptions.
          setStatus(
            data.detail ||
              "Email verification failed."
          );

          return;
        }

        Sentry.addBreadcrumb({
          category: "auth",
          message:
            "Email verification succeeded",
          level: "info",
        });

        setStatus(
          "Email verified successfully. You can now log in."
        );

      } catch (error) {
        console.error(
          "Email verification request failed:",
          error
        );

        Sentry.captureException(
          error,
          {
            tags: {
              operation:
                "email_verification",
            },

            extra: {
              endpoint:
                "/auth/verify-email",
              api_url: API_URL,
            },
          }
        );

        setStatus(
          "Unable to connect to the server."
        );
      }
    }

    verify();
  }, []);

  return (
    <div>
      <h1>
        Email Verification
      </h1>

      <p>
        {status}
      </p>

      {status.includes(
        "successfully"
      ) && (
        <button
          onClick={() => {
            window.location.href =
              "/login";
          }}
        >
          Go to Login
        </button>
      )}
    </div>
  );
}