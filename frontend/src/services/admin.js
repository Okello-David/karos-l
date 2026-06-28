import { api } from './api'

const BASE = '/admin'

export const adminService = {
  // Properties
  propertiesList() {
    return api.get(`${BASE}/properties/`)
  },
  propertyGet(id) {
    return api.get(`${BASE}/properties/${id}/`)
  },
  propertyCreate(data) {
    return api.post(`${BASE}/properties/`, data)
  },
  propertyUpdate(id, data) {
    return api.put(`${BASE}/properties/${id}/`, data)
  },
  propertyPatch(id, data) {
    return api.patch(`${BASE}/properties/${id}/`, data)
  },
  propertyArchive(id) {
    return api.post(`${BASE}/properties/${id}/archive/`)
  },

  // Sections
  sectionsList(params = {}) {
    const query = params.property_id ? `?property_id=${params.property_id}` : ''
    return api.get(`${BASE}/sections/${query}`)
  },
  sectionGet(id) {
    return api.get(`${BASE}/sections/${id}/`)
  },
  sectionCreate(data) {
    return api.post(`${BASE}/sections/`, data)
  },
  sectionUpdate(id, data) {
    return api.put(`${BASE}/sections/${id}/`, data)
  },
  sectionPatch(id, data) {
    return api.patch(`${BASE}/sections/${id}/`, data)
  },
  sectionArchive(id) {
    return api.post(`${BASE}/sections/${id}/archive/`)
  },
  sectionReorder(orderData) {
    return api.post(`${BASE}/sections/reorder/`, orderData)
  },

  // Units
  unitsList(params = {}) {
    const q = new URLSearchParams()
    if (params.section_id) q.set('section_id', params.section_id)
    if (params.status) q.set('status', params.status)
    const qs = q.toString()
    return api.get(`${BASE}/units/${qs ? `?${qs}` : ''}`)
  },
  unitGet(id) {
    return api.get(`${BASE}/units/${id}/`)
  },
  unitCreate(data) {
    return api.post(`${BASE}/units/`, data)
  },
  unitUpdate(id, data) {
    return api.put(`${BASE}/units/${id}/`, data)
  },
  unitPatch(id, data) {
    return api.patch(`${BASE}/units/${id}/`, data)
  },
  unitArchive(id) {
    return api.post(`${BASE}/units/${id}/archive/`)
  },

  // Pricing Rules
  pricingRulesList(params = {}) {
    const q = new URLSearchParams()
    if (params.unit_id) q.set('unit_id', params.unit_id)
    if (params.billing_mode) q.set('billing_mode', params.billing_mode)
    const qs = q.toString()
    return api.get(`${BASE}/pricing-rules/${qs ? `?${qs}` : ''}`)
  },
  pricingRuleGet(id) {
    return api.get(`${BASE}/pricing-rules/${id}/`)
  },
  pricingRuleCreate(data) {
    return api.post(`${BASE}/pricing-rules/`, data)
  },
  pricingRuleUpdate(id, data) {
    return api.put(`${BASE}/pricing-rules/${id}/`, data)
  },
  pricingRuleDelete(id) {
    return api.delete(`${BASE}/pricing-rules/${id}/`)
  },

  // Users
  usersList() {
    return api.get(`${BASE}/users/`)
  },
  userGet(id) {
    return api.get(`${BASE}/users/${id}/`)
  },
  userCreate(data) {
    return api.post(`${BASE}/users/`, data)
  },
  userUpdate(id, data) {
    return api.put(`${BASE}/users/${id}/`, data)
  },
  userPatch(id, data) {
    return api.patch(`${BASE}/users/${id}/`, data)
  },
  userToggleActive(id) {
    return api.post(`${BASE}/users/${id}/toggle-active/`)
  },
  userGroups() {
    return api.get(`${BASE}/users/groups/`)
  },
}
