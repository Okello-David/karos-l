export function formatUGX(amount) {
  const num = Number(amount)
  if (isNaN(num)) return '—'
  return 'UGX ' + num.toLocaleString('en-UG')
}

export function formatPhone(phone) {
  if (!phone) return '—'
  return phone
}

export function fullName(first, last) {
  return `${first} ${last}`.trim()
}
