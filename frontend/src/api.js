export const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

// Derived from API_URL by converting the protocol: http -> ws,
// https -> wss. Only overridden by VITE_WS_URL if you explicitly
// need the WebSocket endpoint on a different host than the REST
// API (uncommon — usually they're the same server).
export const WS_URL =
  import.meta.env.VITE_WS_URL || API_URL.replace(/^http/, "ws");

let accessToken = null;
let refreshTokenPromise = null; // Tracks an ongoing refresh request to prevent race conditions

export function setAccessToken(token) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

export function clearAccessToken() {
  accessToken = null;
}

async function parseResponse(response) {
  const text = await response.text();

  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text);
  } catch {
    return {
      detail: text,
    };
  }
}

async function refreshAccessToken() {
  // If a refresh is already underway, return that exact same promise instance
  if (refreshTokenPromise) {
    return refreshTokenPromise;
  }

  // Create a new refresh promise tracker
  refreshTokenPromise = (async () => {
    try {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include", // Essential for passing HTTP-only refresh cookies
      });

      if (!response.ok) {
        clearAccessToken();
        return null;
      }

      const data = await response.json();

      if (!data.access_token) {
        clearAccessToken();
        return null;
      }

      setAccessToken(data.access_token);
      return data;
    } catch (error) {
      clearAccessToken();
      return null;
    } finally {
      // Clear the tracker variable so future refreshes can run when needed
      refreshTokenPromise = null;
    }
  })();

  return refreshTokenPromise;
}

export async function apiFetch(endpoint, options = {}, retry = true) {
  const headers = {
    ...(options.headers || {}),
  };

  // Attach the in-memory access token if it exists
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers,
      credentials: "include",
    });

    // If unauthorized and we haven't already attempted a retry for this call
    if (response.status === 401 && retry) {
      const refreshed = await refreshAccessToken();

      // If token refresh was successful, re-try the original API request exactly once
      if (refreshed) {
        const retryHeaders = {
          ...(options.headers || {}),
          Authorization: `Bearer ${refreshed.access_token}`,
        };

        return fetch(`${API_URL}${endpoint}`, {
          ...options,
          headers: retryHeaders,
          credentials: "include",
        });
      }
    }

    return response;
  } catch (error) {
    // Handle network or unexpected runtime errors gracefully
    throw error;
  }
}

export async function register(email, password) {
  return apiFetch("/auth/register", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
    }),
  }, false); // Set retry to false to prevent loop on public registration endpoint
}

export async function login(email, password) {
  const response = await apiFetch("/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
    }),
  }, false); // Set retry to false to prevent loop on initial login

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Login failed");
  }

  if (data.access_token) {
    setAccessToken(data.access_token);
  }

  return data;
}

export async function logout() {
  try {
    await apiFetch("/auth/logout", {
      method: "POST",
    });
  } finally {
    clearAccessToken();
  }
}

export async function refreshSession() {
  return refreshAccessToken();
}

export async function getCurrentUser() {
  const response = await apiFetch("/auth/me");

  if (!response.ok) {
    return null;
  }

  return parseResponse(response);
}

export async function verifyEmail(token) {
  const response = await fetch(
    `${API_URL}/auth/verify-email?token=${encodeURIComponent(token)}`,
    {
      credentials: "include",
    }
  );

  return {
    response,
    data: await parseResponse(response),
  };
}
   export async function googleLogin(credential) {
     const response = await apiFetch("/auth/google", {
       method: "POST",
       headers: { "Content-Type": "application/json" },
       body: JSON.stringify({ credential }),
     }, false);

     const data = await parseResponse(response);

     if (!response.ok) {
       throw new Error(data.detail || "Google sign-in failed");
     }

     if (data.access_token) {
       setAccessToken(data.access_token);
     }

     return data;
   }