import { api } from './api'

export const paymentsService = {
  list(params = {}) {
    const query = new URLSearchParams()
    if (params.search) query.set('search', params.search)
    if (params.property_id) query.set('property_id', params.property_id)
    if (params.student_id) query.set('student_id', params.student_id)
    if (params.payment_method) query.set('payment_method', params.payment_method)
    if (params.date_from) query.set('date_from', params.date_from)
    if (params.date_to) query.set('date_to', params.date_to)
    if (params.page) query.set('page', params.page)
    if (params.page_size) query.set('page_size', params.page_size)
    const qs = query.toString()
    return api.get(`/payments/${qs ? `?${qs}` : ''}`)
  },

  get(id) {
    return api.get(`/payments/${id}/`)
  },

  create(data) {
    return api.post('/payments/', data)
  },

  studentBalance(studentId) {
    return api.get(`/payments/student_balance/?student_id=${studentId}`)
  },

  overdue() {
    return api.get('/payments/overdue/')
  },

  receiptsList(params = {}) {
    const query = new URLSearchParams()
    if (params.search) query.set('search', params.search)
    if (params.date_from) query.set('date_from', params.date_from)
    if (params.date_to) query.set('date_to', params.date_to)
    if (params.page) query.set('page', params.page)
    if (params.page_size) query.set('page_size', params.page_size)
    const qs = query.toString()
    return api.get(`/payments/receipts/${qs ? `?${qs}` : ''}`)
  },

  receiptGet(id) {
    return api.get(`/payments/receipts/${id}/`)
  },

  receiptPdfUrl(id) {
    return `/api/payments/receipts/${id}/pdf/`
  },

  receiptPdf(id) {
    return api.blob(`/payments/receipts/${id}/pdf/`)
  },
}
