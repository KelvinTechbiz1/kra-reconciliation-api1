export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

const TOKEN_KEY = "access_token";

export function getToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem(TOKEN_KEY);
  }
  return null;
}

export function setToken(token: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem(TOKEN_KEY, token);
    document.cookie = `${TOKEN_KEY}=${token}; path=/; SameSite=Lax`;
  }
}

export function removeToken() {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
    document.cookie = `${TOKEN_KEY}=; path=/; max-age=0`;
  }
}

export async function fetchWithAuth(endpoint: string, options: RequestInit = {}) {
  const token = getToken();

  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    // Only a 401 means the auth session is actually invalid/expired. Other
    // 4xx (e.g. 403 "no company", 404 "no SAP connection") are domain errors
    // and must NOT log the user out — the caller surfaces them instead.
    if (response.status === 401) {
      removeToken();
      if (typeof window !== "undefined" && window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
      throw new Error("Session expired. Please log in again.");
    }

    return response;
  } catch (err: unknown) {
    if (err instanceof Error && (err.name === "TypeError" || err.message.includes("fetch") || err.message.includes("Failed to fetch"))) {
      throw new Error(`Unable to connect to backend server at ${API_BASE_URL}. Please ensure the backend service is running.`);
    }
    throw err;
  }
}
