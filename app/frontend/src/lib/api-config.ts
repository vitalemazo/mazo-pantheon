/**
 * Centralized API configuration
 * 
 * This module provides the API base URL that works in all environments:
 * - Local development (localhost:8000)
 * - Docker on Unraid (tower.local.lan:8000)
 * - Any other deployment
 * 
 * The URL is determined by:
 * 1. VITE_API_URL environment variable (if set)
 * 2. Same host as the frontend, port 8000 (auto-detect)
 */

function getApiBaseUrl(): string {
  // First check for explicit environment variable
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  
  // Auto-detect based on current browser location
  // If we're on tower.local.lan:5173, API is tower.local.lan:8000
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8000`;
  }
  
  // Fallback for SSR or unknown environments
  return 'http://localhost:8000';
}

export const API_BASE_URL = getApiBaseUrl();

// Helper to construct full API URLs
export function apiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${cleanPath}`;
}
