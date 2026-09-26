const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

let accessToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;

const AUTH_PUBLIC_PATHS = new Set([
  "/api/v1/auth/login",
  "/api/v1/auth/register",
  "/api/v1/auth/verify",
  "/api/v1/auth/refresh",
  "/api/v1/auth/2fa/verify-login",
]);

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function clearClientAuth(): void {
  accessToken = null;
  if (typeof window !== "undefined") {
    sessionStorage.removeItem("sharem_2fa_challenge");
  }
}

export async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const response = await fetch(API_BASE_URL + "/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "ShareM-Int-Xpo",
        },
      });
      if (!response.ok) {
        accessToken = null;
        return false;
      }

      const body = await response.json();
      if (!body.access_token) {
        accessToken = null;
        return false;
      }

      accessToken = body.access_token;
      return true;
    } catch {
      accessToken = null;
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  allowRefresh = true,
): Promise<T> {
  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;
  const headers = new Headers(init.headers);
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken && !AUTH_PUBLIC_PATHS.has(path)) {
    headers.set("Authorization", "Bearer " + accessToken);
  }

  let response: Response;
  try {
    response = await fetch(API_BASE_URL + path, {
      ...init,
      headers,
      credentials: "include",
    });
  } catch {
    throw new Error(
      "Unable to reach the API. Check the backend URL and network connection.",
    );
  }

  if (
    response.status === 401 &&
    allowRefresh &&
    !AUTH_PUBLIC_PATHS.has(path)
  ) {
    if (await refreshAccessToken()) {
      return request<T>(path, init, false);
    }
  }

  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json")
    ? await response.json().catch(() => ({}))
    : {};
  if (!response.ok) {
    throw new Error(body.detail || body.message || "Request failed");
  }
  if (response.status === 204) return undefined as T;
  return body as T;
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  return request<T>(path, init);
}

export async function apiDownload(path: string): Promise<Blob> {
  let response: Response;
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", "Bearer " + accessToken);

  try {
    response = await fetch(API_BASE_URL + path, {
      headers,
      credentials: "include",
    });
  } catch {
    throw new Error("Unable to reach the API.");
  }

  if (response.status === 401 && await refreshAccessToken()) {
    const retryHeaders = new Headers();
    const retryToken = accessToken;
    if (retryToken) retryHeaders.set("Authorization", "Bearer " + retryToken);
    response = await fetch(API_BASE_URL + path, {
      headers: retryHeaders,
      credentials: "include",
    });
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || body.message || "Download failed");
  }
  return response.blob();
}

export { API_BASE_URL };
