const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

let refreshInFlight: Promise<boolean> | null = null;

function getAccessToken(): string | null {
  return typeof window !== "undefined" ? sessionStorage.getItem("sharem_access_token") : null;
}

function getRefreshToken(): string | null {
  return typeof window !== "undefined" ? sessionStorage.getItem("sharem_refresh_token") : null;
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    try {
      const response = await fetch(API_BASE_URL + "/api/v1/auth/refresh", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({refresh_token: refreshToken}),
      });
      if (!response.ok) return false;
      const body = await response.json();
      if (!body.access_token || !body.refresh_token) return false;
      sessionStorage.setItem("sharem_access_token", body.access_token);
      sessionStorage.setItem("sharem_refresh_token", body.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

async function request<T>(path: string, init: RequestInit = {}, allowRefresh = true): Promise<T> {
  const accessToken = getAccessToken();
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  const headers = new Headers(init.headers);
  if (!isFormData && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", "Bearer " + accessToken);

  let response: Response;
  try {
    response = await fetch(API_BASE_URL + path, {...init, headers});
  } catch {
    throw new Error("Unable to reach the API. Check the backend URL and network connection.");
  }

  if (response.status === 401 && allowRefresh && !path.startsWith("/api/v1/auth/")) {
    if (await refreshAccessToken()) return request<T>(path, init, false);
  }

  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json().catch(() => ({})) : {};
  if (!response.ok) throw new Error(body.detail || body.message || "Request failed");
  if (response.status === 204) return undefined as T;
  return body as T;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>(path, init);
}

export async function apiDownload(path: string): Promise<Blob> {
  const headers = new Headers();
  const accessToken = getAccessToken();
  if (accessToken) headers.set("Authorization", "Bearer " + accessToken);
  let response: Response;
  try {
    response = await fetch(API_BASE_URL + path, {headers});
  } catch {
    throw new Error("Unable to reach the API.");
  }
  if (response.status === 401 && await refreshAccessToken()) {
    const retryHeaders = new Headers();
    const retryToken = getAccessToken();
    if (retryToken) retryHeaders.set("Authorization", "Bearer " + retryToken);
    response = await fetch(API_BASE_URL + path, {headers: retryHeaders});
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || body.message || "Download failed");
  }
  return response.blob();
}

export { API_BASE_URL };