import { api } from './api'

export const propertyService = {
  list() {
    return api.get('/properties/')
  },
}

export const sectionService = {
  list(propertyId) {
    const query = propertyId ? `?property=${propertyId}` : ''
    return api.get(`/sections/${query}`)
  },
}

export const unitService = {
  list(sectionId) {
    const query = sectionId ? `?section=${sectionId}` : ''
    return api.get(`/units/${query}`)
  },
}
