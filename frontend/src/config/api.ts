// API Configuration
// Supports both Lambda and ECS backends with environment variable toggle

const USE_ECS = import.meta.env.VITE_USE_ECS === 'true';
const API_URL_LAMBDA = import.meta.env.VITE_API_URL_LAMBDA || '';
const API_URL_ECS = import.meta.env.VITE_API_URL_ECS || '';

// Fallback to old VITE_API_URL for backward compatibility
const LEGACY_API_URL = import.meta.env.VITE_API_URL || '';

// Select backend based on VITE_USE_ECS flag
const getApiUrl = (): string => {
  if (USE_ECS && API_URL_ECS) {
    return API_URL_ECS;
  }
  if (API_URL_LAMBDA) {
    return API_URL_LAMBDA;
  }
  // Fallback to legacy or localhost
  return LEGACY_API_URL || 'http://localhost:8000';
};

export const API_BASE = `${getApiUrl()}/api`;

// Log which backend is being used (helpful for debugging)
console.log(`[API Config] Using ${USE_ECS ? 'ECS' : 'Lambda'} backend: ${API_BASE}`);
