/**
 * api.js — Axios instance and API helpers.
 *
 * The Vite dev server proxies /api/* to http://localhost:8000,
 * so we use a relative base URL here (works in both dev and prod builds).
 */
import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Interceptors ─────────────────────────────────────────────────────────────

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('[API Error]', error?.response?.data || error.message)
    return Promise.reject(error)
  }
)

// ── Health ────────────────────────────────────────────────────────────────────

/** GET /api/health */
export async function getHealth() {
  const { data } = await apiClient.get('/health')
  return data
}

// ── Dataset ───────────────────────────────────────────────────────────────────

/** GET /api/dataset/stats */
export async function getDatasetStats() {
  const { data } = await apiClient.get('/dataset/stats')
  return data
}

/** POST /api/dataset/import */
export async function triggerImport() {
  const { data } = await apiClient.post('/dataset/import')
  return data
}

// ── Products ──────────────────────────────────────────────────────────────────

/** GET /api/products */
export async function getProducts() {
  const { data } = await apiClient.get('/products')
  return data
}

// ── Reviews ───────────────────────────────────────────────────────────────────

/**
 * GET /api/reviews
 * @param {number} page
 * @param {number} limit
 * @param {string|null} productId
 */
export async function getReviews({ page = 1, limit = 20, productId = null } = {}) {
  const params = { page, limit }
  if (productId) params.product_id = productId
  const { data } = await apiClient.get('/reviews', { params })
  return data
}

// ── Sales ─────────────────────────────────────────────────────────────────────

/**
 * GET /api/sales
 * @param {number} page
 * @param {number} limit
 * @param {string|null} productId
 */
export async function getSales({ page = 1, limit = 20, productId = null } = {}) {
  const params = { page, limit }
  if (productId) params.product_id = productId
  const { data } = await apiClient.get('/sales', { params })
  return data
}

export default apiClient
