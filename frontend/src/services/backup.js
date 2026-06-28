import { api } from './api'

const BASE = '/backups'

export const backupService = {
  list(params = {}) {
    const q = new URLSearchParams()
    if (params.page) q.set('page', params.page)
    if (params.page_size) q.set('page_size', params.page_size)
    const qs = q.toString()
    return api.get(`${BASE}/${qs ? `?${qs}` : ''}`)
  },

  get(id) {
    return api.get(`${BASE}/${id}/`)
  },

  create(data = {}) {
    return api.post(`${BASE}/`, data)
  },

  restore(id, data) {
    return api.post(`${BASE}/${id}/restore/`, data)
  },

  validate(id) {
    return api.get(`${BASE}/${id}/validate/`)
  },

  exportData(entity, fileFormat) {
    return fetch(`/api${BASE}/export/?entity=${entity}&file_format=${fileFormat}`, {
      headers: {
        Authorization: `Token ${localStorage.getItem('auth_token')}`,
      },
    }).then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Export failed with status ${res.status}`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${entity}.${fileFormat}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    })
  },
}
