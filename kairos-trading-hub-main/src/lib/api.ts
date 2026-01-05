/**
 * API configuration and helper functions
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Constructs a full API URL from a relative path
 * @param path - API path (e.g., '/api/watchlist' or 'api/watchlist')
 * @returns Full URL including base URL
 */
export function getApiUrl(path: string): string {
    // Remove leading slash if present for consistency
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${API_BASE_URL}${normalizedPath}`;
}

/**
 * Makes a fetch request to the API with proper URL construction
 * @param path - API path
 * @param options - Fetch options
 * @returns Fetch response
 */
export async function apiFetch(path: string, options?: RequestInit): Promise<Response> {
    return fetch(getApiUrl(path), options);
}
