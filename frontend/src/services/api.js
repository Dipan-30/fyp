/**
 * api.js — Axios instance and API helpers.
 *
 * The Vite dev server proxies /api/* to http://localhost:8000,
 * so we use a relative base URL here (works in both dev and prod builds).
 */
import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Interceptors ─────────────────────────────────────────────────────────────

// Log request errors in development
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('[API Error]', error?.response?.data || error.message)
    return Promise.reject(error)
  }
)

// ── Endpoint helpers ──────────────────────────────────────────────────────────

/**
 * GET /api/health — verify the backend is running.
 * @returns {Promise<{status: string, app: string, version: string}>}
 */
export async function getHealth() {
  const { data } = await apiClient.get('/health')
  return data
}

export default apiClient
