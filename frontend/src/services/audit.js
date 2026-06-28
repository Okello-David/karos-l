import { api } from './api'

const BASE = '/audit'

export const auditService = {
  list(params = {}) {
    const q = new URLSearchParams()
    if (params.entity_type) q.set('entity_type', params.entity_type)
    if (params.action) q.set('action', params.action)
    if (params.actor_id) q.set('actor_id', params.actor_id)
    if (params.date_from) q.set('date_from', params.date_from)
    if (params.date_to) q.set('date_to', params.date_to)
    if (params.page) q.set('page', params.page)
    if (params.page_size) q.set('page_size', params.page_size)
    const qs = q.toString()
    return api.get(`${BASE}/${qs ? `?${qs}` : ''}`)
  },

  get(id) {
    return api.get(`${BASE}/${id}/`)
  },

  entityTypes() {
    return api.get(`${BASE}/entity-types/`)
  },

  actions() {
    return api.get(`${BASE}/actions/`)
  },
}
