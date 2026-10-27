/**
 * Industrial API Client for UC-RT-03 Markdown Optimization
 * 
 * Session Strategy & Security Architecture:
 * - Primary: SameSite=Lax HttpOnly cookies (access_token, refresh_token) set by FastAPI backend.
 *   This mitigates browser XSS exfiltration of tokens.
 * - In-Memory Fallback: Active access token kept in JavaScript memory during active tab lifecycle.
 * - Refresh Token Rotation: Refreshed seamlessly on 401 Unauthorized responses.
 * - Threat Model: Tokens are NEVER persisted in unencrypted localStorage to eliminate persistent
 *   storage leakage.
 */

import type { ApiErrorResponse, TokenResponse } from '../types/auth';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

let inMemoryAccessToken: string | null = null;
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

function onRefreshed(token: string): void {
  refreshSubscribers.forEach((callback) => callback(token));
  refreshSubscribers = [];
}

function addRefreshSubscriber(callback: (token: string) => void): void {
  refreshSubscribers.push(callback);
}

export class ApiError extends Error {
  code: string;
  status: number;
  details?: Record<string, unknown>;

  constructor(status: number, message: string, code: string = 'API_ERROR', details?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  // Attach in-memory bearer token if present
  if (inMemoryAccessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${inMemoryAccessToken}`);
  }

  // Always include credentials so HttpOnly cookies are transported
  const fetchOptions: RequestInit = {
    ...options,
    headers,
    credentials: 'include',
  };

  let response: Response;
  try {
    response = await fetch(url, fetchOptions);
  } catch (err) {
    throw new ApiError(0, 'Unable to connect to optimization server. Verify backend is running.', 'NETWORK_ERROR');
  }

  // Handle 401 Unauthorized with token refresh (except for login/signup/refresh endpoints)
  if (response.status === 401 && !endpoint.startsWith('/auth/login') && !endpoint.startsWith('/auth/signup') && !endpoint.startsWith('/auth/refresh')) {
    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshResponse = await fetch(`${BASE_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
        });

        if (refreshResponse.ok) {
          const tokenData: TokenResponse = await refreshResponse.json();
          setAccessToken(tokenData.access_token);
          isRefreshing = false;
          onRefreshed(tokenData.access_token);

          // Retry the original request
          headers.set('Authorization', `Bearer ${tokenData.access_token}`);
          return apiClient<T>(endpoint, { ...options, headers });
        } else {
          isRefreshing = false;
          setAccessToken(null);
          window.dispatchEvent(new CustomEvent('auth:session-expired'));
          throw new ApiError(401, 'Session expired. Please log in again.', 'SESSION_EXPIRED');
        }
      } catch (err) {
        isRefreshing = false;
        setAccessToken(null);
        window.dispatchEvent(new CustomEvent('auth:session-expired'));
        throw new ApiError(401, 'Session expired. Please log in again.', 'SESSION_EXPIRED');
      }
    } else {
      // Queue concurrent request until refresh finishes
      return new Promise<T>((resolve, reject) => {
        addRefreshSubscriber((newToken: string) => {
          headers.set('Authorization', `Bearer ${newToken}`);
          apiClient<T>(endpoint, { ...options, headers })
            .then(resolve)
            .catch(reject);
        });
      });
    }
  }

  // Parse response
  if (!response.ok) {
    let errorData: ApiErrorResponse | null = null;
    let message = 'An error occurred during the request.';
    let code = `HTTP_${response.status}`;

    try {
      errorData = await response.json();
      if (errorData?.error) {
        message = errorData.error.message || message;
        code = errorData.error.code || code;
      }
    } catch {
      message = response.statusText || message;
    }

    throw new ApiError(response.status, message, code, errorData?.error?.details);
  }

  // 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}
