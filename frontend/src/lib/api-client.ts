import { getSession } from 'next-auth/react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || ''

/**
 * A robust API client that handles authentication and base path resolution.
 * @param endpoint The API endpoint to call, e.g., '/api/test' or '/api/admin/dashboard'.
 *                 The endpoint should include the '/api' prefix.
 * @param options Standard fetch options (method, body, etc.).
 */
async function apiClientFetch<T = unknown>(
  endpoint: string,
  options: RequestInit = {},
  timeoutMs?: number,
): Promise<T> {
  const session = await getSession()

  const headers = new Headers(options.headers || {})

  if (session?.accessToken) {
    headers.set('Authorization', `Bearer ${session.accessToken}`)
  }

  // Construct the full URL
  const fullUrl = `${API_URL}${BASE_PATH}${endpoint}`

  // Set up optional AbortController timeout so browser never hangs indefinitely
  let controller: AbortController | undefined
  let timeoutId: ReturnType<typeof setTimeout> | undefined
  if (timeoutMs) {
    controller = new AbortController()
    timeoutId = setTimeout(() => controller!.abort(), timeoutMs)
  }

  try {
    const response = await fetch(fullUrl, {
      ...options,
      headers,
      signal: controller?.signal,
    })

    // If the backend returns a 401, log it but don't force redirect in dev mode
    if (response.status === 401) {
      console.warn('[API] 401 Unauthorized — check backend AUTH_BYPASS setting')
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({
        detail: response.statusText,
      }))
      throw new Error(errorData.detail || 'An API error occurred.')
    }

    // Handle responses with no content
    if (response.status === 204) {
      return null as T
    }

    return response.json() as Promise<T>
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Request timed out. The AI is taking longer than expected — please try again.')
    }
    throw err
  } finally {
    if (timeoutId) clearTimeout(timeoutId)
  }
}

/**
 * API client with convenience methods for common HTTP operations.
 */
export const apiClient = {
  /**
   * Perform a GET request.
   */
  get: <T = unknown>(endpoint: string, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, { ...options, method: 'GET' })
  },

  /**
   * Perform a POST request.
   */
  post: <T = unknown>(endpoint: string, data?: unknown, options?: RequestInit, timeoutMs?: number): Promise<T> => {
    return apiClientFetch<T>(endpoint, {
      ...options,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
    }, timeoutMs)
  },

  /**
   * Perform a PUT request.
   */
  put: <T = unknown>(endpoint: string, data?: unknown, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, {
      ...options,
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
    })
  },

  /**
   * Perform a PATCH request.
   */
  patch: <T = unknown>(endpoint: string, data?: unknown, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, {
      ...options,
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
    })
  },

  /**
   * Perform a DELETE request.
   */
  delete: <T = unknown>(endpoint: string, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, { ...options, method: 'DELETE' })
  },
}

// Default export for backward compatibility
export default apiClientFetch
