/**
 * Central API client. Every backend call goes through here so the base
 * URL and error handling are defined in exactly one place.
 *
 * VITE_API_BASE_URL is read at build time (see .env.example at the
 * frontend root). Defaults to the local FastAPI dev server.
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: options.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!res.ok) {
    let detail = null
    try {
      detail = (await res.json()).detail
    } catch {
      /* response wasn't JSON */
    }
    throw new ApiError(detail || `Request failed (${res.status})`, res.status, detail)
  }

  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) return res.json()
  return res.blob()
}

function qs(params = {}) {
  const usp = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    if (Array.isArray(value)) {
      value.forEach((v) => usp.append(key, v))
    } else {
      usp.append(key, value)
    }
  })
  const str = usp.toString()
  return str ? `?${str}` : ''
}

export const api = {
  // ---- Cities ----
  listCities: () => request('/cities'),
  getCitySummary: (cityId) => request(`/cities/${cityId}/summary`),
  listWards: (cityId) => request(`/cities/${cityId}/wards`),

  // ---- Problems ----
  listProblems: (params) => request(`/problems${qs(params)}`),
  getProblem: (id) => request(`/problems/${id}`),
  updateProblemStatus: (id, status, notes) =>
    request(`/problems/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status, notes }) }),

  // ---- Map ----
  getMapProblems: (params) => request(`/map/problems${qs(params)}`),

  // ---- Inspect & Analyze ----
  analyzeImage: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/analyze/image', { method: 'POST', body: form })
  },
  verifyDetection: (detectionId, payload) =>
    request(`/detections/${detectionId}/verify`, { method: 'POST', body: JSON.stringify(payload) }),
  createManualProblem: (payload) => request('/problems/manual', { method: 'POST', body: JSON.stringify(payload) }),

  // ---- Analytics ----
  getOverview: (cityId) => request(`/analytics/overview${qs({ city_id: cityId })}`),
  getTrends: (cityId, granularity = 'week') => request(`/analytics/trends${qs({ city_id: cityId, granularity })}`),
  getHotspots: (cityId) => request(`/analytics/hotspots${qs({ city_id: cityId })}`),
  getRecurring: (cityId) => request(`/analytics/recurring${qs({ city_id: cityId })}`),

  // ---- Risk / Action Center ----
  getPriorities: (cityId, limit = 20, unresolvedOnly = true) =>
    request(`/risk/priorities${qs({ city_id: cityId, limit, unresolved_only: unresolvedOnly })}`),
  getRiskDetail: (problemId) => request(`/risk/${problemId}`),

  // ---- AI Recommendations & Advice ----
  getRecommendations: (cityId) => request(`/recommendations${qs({ city_id: cityId })}`),
  sendChatMessage: (payload) => request('/chat', { method: 'POST', body: JSON.stringify(payload) }),

  // ---- Reports ----
  downloadReport: (cityId, format, days = 30) =>
    request('/reports', { method: 'POST', body: JSON.stringify({ city_id: cityId, format, days }) }),

  uploadsUrl: (path) => `${BASE_URL.replace(/\/api\/v1$/, '')}${path}`,
  getMlStatus: () => request('/ml/status'),
}
