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

/** GET /api/products/:id */
export async function getProductOverview(id) {
  const { data } = await apiClient.get(`/products/${id}`)
  return data
}

/** GET /api/products/:id/sales */
export async function getProductSales(id) {
  const { data } = await apiClient.get(`/products/${id}/sales`)
  return data
}

/** GET /api/products/:id/sentiment */
export async function getProductSentiment(id) {
  const { data } = await apiClient.get(`/products/${id}/sentiment`)
  return data
}

/** GET /api/products/:id/forecast */
export async function getProductForecast(id) {
  const { data } = await apiClient.get(`/products/${id}/forecast`)
  return data
}



// ── Research (Phase 9) ────────────────────────────────────────────────────────

/** GET /api/research/summary */
export async function getResearchSummary() {
  const { data } = await apiClient.get('/research/summary')
  return data
}



export default apiClient
