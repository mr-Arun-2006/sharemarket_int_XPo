import { API_BASE_URL, setAccessToken } from "./api";

type FirebaseSession = {
  idToken: string;
  refreshToken: string;
  expiresAt: number;
  email: string;
  uid: string;
};

type FirebaseTokenResponse = {
  idToken: string;
  refreshToken: string;
  expiresIn: string;
  email: string;
  localId: string;
};

type FirebaseLookupResponse = {
  users?: Array<{
    localId: string;
    email?: string;
    emailVerified?: boolean;
  }>;
};

export type AppSessionResponse = {
  status: string;
  access_token?: string;
  challenge_id?: string;
  requires_2fa?: boolean;
};

const FIREBASE_AUTH_BASE = "https://identitytoolkit.googleapis.com/v1";
const FIREBASE_TOKEN_URL = "https://securetoken.googleapis.com/v1/token";
const FIREBASE_SESSION_KEY = "sharem_firebase_session";

function apiKey(): string {
  const value = process.env.NEXT_PUBLIC_FIREBASE_API_KEY;
  if (!value) {
    throw new Error("Firebase is not configured. Add NEXT_PUBLIC_FIREBASE_API_KEY to the frontend Vercel project.");
  }
  return value;
}

function firebaseErrorMessage(code: string): string {
  const messages: Record<string, string> = {
    EMAIL_EXISTS: "An account with this email already exists. Sign in instead.",
    INVALID_EMAIL: "Enter a valid email address.",
    INVALID_LOGIN_CREDENTIALS: "Email or password is incorrect.",
    EMAIL_NOT_FOUND: "Email or password is incorrect.",
    INVALID_PASSWORD: "Email or password is incorrect.",
    USER_DISABLED: "This account has been disabled. Contact the administrator.",
    OPERATION_NOT_ALLOWED: "Enable Email/Password sign-in in Firebase Authentication.",
    WEAK_PASSWORD: "Choose a stronger password with at least 6 characters.",
    TOO_MANY_ATTEMPTS_TRY_LATER: "Too many attempts. Try again later.",
    EXPIRED_OOB_CODE: "The verification link has expired. Request a new verification email.",
    INVALID_ID_TOKEN: "Your Firebase session expired. Sign in again.",
    EMAIL_NOT_VERIFIED: "Verify your email before signing in.",
  };
  return messages[code] || "Firebase authentication failed. Check your Firebase project configuration.";
}

async function parseFirebaseError(response: Response): Promise<never> {
  const payload = await response.json().catch(() => ({}));
  const code = String(payload?.error?.message || "FIREBASE_AUTH_ERROR").split(" : ")[0];
  throw new Error(firebaseErrorMessage(code));
}

async function firebasePost<T>(method: string, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(
    FIREBASE_AUTH_BASE + "/" + method + "?key=" + encodeURIComponent(apiKey()),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) return parseFirebaseError(response);
  return response.json() as Promise<T>;
}

function readSession(): FirebaseSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(FIREBASE_SESSION_KEY);
    return raw ? (JSON.parse(raw) as FirebaseSession) : null;
  } catch {
    return null;
  }
}

function saveSession(payload: FirebaseTokenResponse): FirebaseSession {
  const session: FirebaseSession = {
    idToken: payload.idToken,
    refreshToken: payload.refreshToken,
    expiresAt: Date.now() + Number(payload.expiresIn || 3600) * 1000,
    email: payload.email,
    uid: payload.localId,
  };
  window.sessionStorage.setItem(FIREBASE_SESSION_KEY, JSON.stringify(session));
  return session;
}

export function getFirebaseSessionEmail(): string {
  return readSession()?.email || "";
}

export function clearFirebaseSession(): void {
  if (typeof window !== "undefined") {
    window.sessionStorage.removeItem(FIREBASE_SESSION_KEY);
  }
}

export async function createFirebaseAccount(email: string, password: string): Promise<void> {
  const result = await firebasePost<FirebaseTokenResponse>("accounts:signUp", {
    email: email.trim(),
    password,
    returnSecureToken: true,
  });
  saveSession(result);
  await sendFirebaseVerificationEmail();
}

export async function signInWithFirebase(email: string, password: string): Promise<boolean> {
  const result = await firebasePost<FirebaseTokenResponse>("accounts:signInWithPassword", {
    email: email.trim(),
    password,
    returnSecureToken: true,
  });
  saveSession(result);
  return checkFirebaseEmailVerified();
}

async function refreshFirebaseToken(force = false): Promise<string> {
  const current = readSession();
  if (!current) {
    throw new Error("Your Firebase session is missing. Sign in again.");
  }

  if (!force && current.expiresAt > Date.now() + 60_000) {
    return current.idToken;
  }

  const response = await fetch(FIREBASE_TOKEN_URL + "?key=" + encodeURIComponent(apiKey()), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: current.refreshToken,
    }),
  });

  if (!response.ok) {
    clearFirebaseSession();
    return parseFirebaseError(response);
  }

  const payload = await response.json();
  const updated: FirebaseSession = {
    idToken: payload.id_token,
    refreshToken: payload.refresh_token,
    expiresAt: Date.now() + Number(payload.expires_in || 3600) * 1000,
    email: current.email,
    uid: payload.user_id || current.uid,
  };
  window.sessionStorage.setItem(FIREBASE_SESSION_KEY, JSON.stringify(updated));
  return updated.idToken;
}

async function lookupFirebaseUser(idToken: string): Promise<{localId:string;email?:string;emailVerified?:boolean}> {
  const response = await firebasePost<FirebaseLookupResponse>("accounts:lookup", { idToken });
  const user = response.users?.[0];
  if (!user) throw new Error("Firebase user profile was not found.");
  return user;
}

export async function checkFirebaseEmailVerified(): Promise<boolean> {
  const idToken = await refreshFirebaseToken(true);
  const user = await lookupFirebaseUser(idToken);
  return user.emailVerified === true;
}

export async function sendFirebaseVerificationEmail(): Promise<void> {
  const idToken = await refreshFirebaseToken();
  const response = await fetch(
    FIREBASE_AUTH_BASE + "/accounts:sendOobCode?key=" + encodeURIComponent(apiKey()),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        requestType: "VERIFY_EMAIL",
        idToken,
        continueUrl: typeof window !== "undefined" ? window.location.origin + "/verify" : undefined,
      }),
    },
  );
  if (!response.ok) return parseFirebaseError(response);
}

export async function exchangeFirebaseSession(): Promise<AppSessionResponse> {
  const idToken = await refreshFirebaseToken(true);
  const user = await lookupFirebaseUser(idToken);
  if (user.emailVerified !== true) {
    throw new Error(firebaseErrorMessage("EMAIL_NOT_VERIFIED"));
  }

  const response = await fetch(API_BASE_URL + "/api/v1/auth/firebase/exchange", {
    method: "POST",
    credentials: "include",
    headers: {
      Authorization: "Bearer " + idToken,
      "Content-Type": "application/json",
      "X-Requested-With": "ShareM-Int-Xpo",
    },
    body: "{}",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "Unable to create the application session.");
  }

  clearFirebaseSession();
  if (payload.access_token) setAccessToken(payload.access_token);
  return payload as AppSessionResponse;
}
