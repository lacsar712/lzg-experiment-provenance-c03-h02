import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') {
      err.message = detail
    } else if (Array.isArray(detail)) {
      err.message = detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
    }
    return Promise.reject(err)
  },
)

export async function login(username, password) {
  const { data } = await api.post('/auth/login', { username, password })
  return data
}

export async function listRuns(params = {}) {
  const { data } = await api.get('/runs', { params })
  return data
}

export async function getRun(id) {
  const { data } = await api.get(`/runs/${id}`)
  return data
}

export async function createRun(body) {
  const { data } = await api.post('/runs', body)
  return data
}

export async function recordMetric(id, body) {
  const { data } = await api.post(`/runs/${id}/metrics`, body)
  return data
}

export async function attachArtifact(id, body) {
  const { data } = await api.post(`/runs/${id}/artifacts`, body)
  return data
}

export async function completeRun(id, body) {
  const { data } = await api.post(`/runs/${id}/complete`, body)
  return data
}

export async function abortRun(id, body) {
  const { data } = await api.post(`/runs/${id}/abort`, body)
  return data
}

export async function getEvents(id) {
  const { data } = await api.get(`/runs/${id}/events`)
  return data
}

export async function getLineage(id) {
  const { data } = await api.get(`/runs/${id}/lineage`)
  return data
}

export default api
