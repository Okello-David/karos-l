import { api } from './api'

export const occupancyService = {
  list(params = {}) {
    const query = new URLSearchParams()
    if (params.student_id) query.set('student_id', params.student_id)
    if (params.unit_id) query.set('unit_id', params.unit_id)
    if (params.active_only) query.set('active_only', 'true')
    if (params.page) query.set('page', params.page)
    if (params.page_size) query.set('page_size', params.page_size)
    const qs = query.toString()
    return api.get(`/occupancy/${qs ? `?${qs}` : ''}`)
  },

  get(id) {
    return api.get(`/occupancy/${id}/`)
  },

  assign(data) {
    return api.post('/occupancy/', data)
  },

  update(id, data) {
    return api.patch(`/occupancy/${id}/`, data)
  },

  checkout(id) {
    return api.post(`/occupancy/${id}/checkout/`)
  },

  summary() {
    return api.get('/occupancy/summary/')
  },
}
