const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const accessToken = typeof window !== "undefined" ? sessionStorage.getItem("sharem_access_token") : null;
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const headers: HeadersInit = {
    ...(!isFormData ? {"Content-Type":"application/json"} : {}),
    ...(accessToken ? {Authorization:"Bearer "+accessToken} : {}),
    ...(init?.headers || {}),
  };
  const response = await fetch(API_BASE_URL + path, {...init, headers});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || body.message || "Request failed");
  return body as T;
}

export { API_BASE_URL };


export async function apiDownload(path: string): Promise<Blob> {
  const accessToken = typeof window !== "undefined" ? sessionStorage.getItem("sharem_access_token") : null;
  const response = await fetch(API_BASE_URL + path, {
    headers: accessToken ? { Authorization: "Bearer " + accessToken } : {},
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || body.message || "Download failed");
  }
  return response.blob();
}
