import { api } from './api'

export const explorerService = {
  getHierarchy(search = '') {
    const params = search ? `?search=${encodeURIComponent(search)}` : ''
    return api.get(`/properties/explorer/${params}`)
  },

  getUnitDetail(unitId) {
    return api.get(`/units/${unitId}/detail/`)
  },
}
