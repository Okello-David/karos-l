import { api } from './api'

export const occupantsService = {
  list(params = {}) {
    const query = new URLSearchParams()
    if (params.search) query.set('search', params.search)
    if (params.status) query.set('status', params.status)
    if (params.page) query.set('page', params.page)
    if (params.page_size) query.set('page_size', params.page_size)
    const qs = query.toString()
    return api.get(`/occupants/${qs ? `?${qs}` : ''}`)
  },

  get(id) {
    return api.get(`/occupants/${id}/`)
  },

  create(data) {
    return api.post('/occupants/', data)
  },

  update(id, data) {
    return api.put(`/occupants/${id}/`, data)
  },

  archive(id) {
    return api.post(`/occupants/${id}/archive/`)
  },
}
