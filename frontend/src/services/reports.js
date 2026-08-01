import { api } from './api'

function buildQuery(params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value) query.append(key, value)
  })
  const string = query.toString()
  return string ? `?${string}` : ''
}

// Uses api.blob rather than a bare fetch so the shared auth header, 401
// handling, and error-message extraction all apply here too.
async function download(endpoint, filename) {
  const blob = await api.blob(endpoint)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const reportsService = {
  occupancy: () => api.get('/reports/occupancy/'),

  financial: (params) => api.get(`/reports/financial/${buildQuery(params)}`),

  occupants: () => api.get('/reports/occupants/'),

  export(reportKey, fileFormat, params = {}) {
    const query = buildQuery({ ...params, file_format: fileFormat })
    return download(`/reports/${reportKey}/${query}`, `${reportKey}_report.${fileFormat}`)
  },
}
