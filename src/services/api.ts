import type {
  APIError,
  LoginRequest,
  LoginResponse,
  SalesFilters,
  SalesResponse,
  UploadResponse,
  User,
  ValidationIssue,
} from "../types/api";

const TOKEN_KEY = "salesflow.access-token";
const AUTH_EVENT = "salesflow:unauthorized";
// Vite proxies /api in development; production supports a same-origin reverse proxy.
const baseUrl = (import.meta.env?.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export const session = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
  onUnauthorized: (callback: () => void) => {
    window.addEventListener(AUTH_EVENT, callback);
    return () => window.removeEventListener(AUTH_EVENT, callback);
  },
};

export class ApiError extends Error implements APIError {
  constructor(
    public status: number,
    message: string,
    public issues: ValidationIssue[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseError(status: number, body: unknown): ApiError {
  if (status >= 500)
    return new ApiError(
      status,
      "The server could not complete this request. Please try again.",
    );
  if (status === 401)
    return new ApiError(
      status,
      "Your session has expired. Please sign in again.",
    );
  const detail = isObject(body) ? body.detail : undefined;
  const entries =
    isObject(detail) && Array.isArray(detail.errors)
      ? detail.errors
      : Array.isArray(detail)
        ? detail
        : [];
  const issues: ValidationIssue[] = entries.flatMap((entry: unknown) => {
    if (!isObject(entry)) return [];
    const message =
      typeof entry.message === "string"
        ? entry.message
        : typeof entry.msg === "string"
          ? entry.msg
          : undefined;
    if (!message) return [];
    return [
      {
        message,
        row: typeof entry.row === "number" ? entry.row : undefined,
        column: typeof entry.column === "string" ? entry.column : undefined,
      },
    ];
  });
  return new ApiError(
    status,
    issues.length
      ? "Please correct the following and try again."
      : typeof detail === "string"
        ? detail
        : status === 413
          ? "This file is too large. Choose a smaller workbook."
          : "The request could not be completed. Please try again.",
    issues,
  );
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  const token = authenticated ? session.get() : null;
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, { ...options, headers });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(
      0,
      "Unable to reach the server. Check your connection and try again.",
    );
  }
  // Expire only the session that made this request, never a newer login.
  if (response.status === 401 && authenticated && session.get() === token) {
    session.clear();
    window.dispatchEvent(new Event(AUTH_EVENT));
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw parseError(response.status, body);
  if (body === null)
    throw new ApiError(
      response.status,
      "The server returned an unexpected response. Please try again.",
    );
  return body as T;
}

export const api = {
  login: (data: LoginRequest) =>
    request<LoginResponse>(
      "/api/v1/auth/login",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      },
      false,
    ),
  me: () => request<User>("/api/v1/auth/me"),
  sales: (filters: SalesFilters, signal?: AbortSignal) => {
    const query = new URLSearchParams();
    for (const key of ["start_date", "end_date", "sku_name"] as const) {
      if (filters[key]) query.set(key, filters[key]);
    }
    return request<SalesResponse>(
      `/api/v1/sales${query.size ? `?${query}` : ""}`,
      { signal },
    );
  },
  upload: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    // The browser supplies the multipart boundary. Do not set Content-Type.
    return request<UploadResponse>("/api/v1/sales/upload", {
      method: "POST",
      body,
    });
  },
};
